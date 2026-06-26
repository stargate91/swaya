import os
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor

from app.shared_kernel.enums import ScanMode
from app.domains.library.models import Library, MediaItem, ExtraFile
from app.domains.library.services.scanner.collector import Collector
from app.domains.library.services.scanner.categorizer import Categorizer
from app.domains.library.services.scanner.linker import Linker
from app.domains.library.services.scanner.probe import TechnicalProber
from app.shared_kernel.ports.file_system_port import FileSystemPort
from app.domains.library.services.scanner.analyzer import Analyzer

from app.domains.library.services.scanner.scan_collector.hash_calculator import HashCalculator
from app.domains.library.services.scanner.scan_collector.duplicate_finder import DuplicateFinder
from app.domains.library.services.scanner.scan_collector.file_walker import FileWalker

# Import modular subcomponents
from app.domains.library.services.scanner.scan_collector.video_prober import VideoProber
from app.domains.library.services.scanner.scan_collector.extra_determiner import ExtraDeterminer
from app.domains.library.services.scanner.scan_collector.scan_persister import ScanPersister

logger = logging.getLogger(__name__)

class ScanCollector:
    """
    Handles Phase 1 of scanning: discovers files, probes new videos, 
    links extras to media items, detects renames, and saves everything to the database.
    """

    def __init__(
        self,
        db: Session,
        library: Library,
        prober: Optional[TechnicalProber] = None,
        collector: Optional[Collector] = None,
        categorizer: Optional[Categorizer] = None,
        linker: Optional[Linker] = None,
        analyzer: Optional[Analyzer] = None,
        mode: ScanMode = ScanMode.MOVIES_TV,
        min_video_duration_minutes: float = 10,
        progress_callback: Optional[callable] = None,
        provider: Optional[str] = None,
        fs: Optional[FileSystemPort] = None
    ):
        self.db = db
        self.library = library
        self.prober = prober or TechnicalProber()
        self.collector = collector or Collector()
        self.categorizer = categorizer or Categorizer()
        self.linker = linker or Linker()
        self.analyzer = analyzer or Analyzer()
        self.mode = mode
        self.min_video_duration_minutes = min_video_duration_minutes
        self.progress_callback = progress_callback
        self.provider = str(provider or "").strip().lower()
        if fs is None:
            from app.infrastructure.filesystem.fs_utils import DbFileSystemAdapter
            self.fs = DbFileSystemAdapter()
        else:
            self.fs = fs

        # Instantiate modular subcomponents
        self.hash_calculator = HashCalculator(self.fs)
        self.duplicate_finder = DuplicateFinder(self.library, self.fs)
        self.file_walker = FileWalker(
            library=self.library,
            categorizer=self.categorizer,
            mode=self.mode,
            min_video_duration_minutes=self.min_video_duration_minutes,
            provider=self.provider
        )

        # New instantiated sub-services
        self.video_prober = VideoProber(self.prober, self.hash_calculator, self.analyzer, self.mode)
        self.extra_determiner = ExtraDeterminer(self.categorizer, self.mode)
        self.scan_persister = ScanPersister(db, library, mode, self.hash_calculator, self.duplicate_finder, self.analyzer)

    def _duration_limit_seconds(self) -> float:
        return self.file_walker.duration_limit_seconds(self.db)

    def _should_force_video_to_extra(self, path: Path) -> bool:
        return self.file_walker.should_force_video_to_extra(path, self.db)

    def _probe_and_analyze_target(self, filepath: Path) -> Dict[str, Any]:
        return self.video_prober.probe_and_analyze_target(filepath)

    def collect_and_save(self) -> Tuple[List[MediaItem], Dict[str, Dict[str, Any]]]:
        """
        Discovers files, filters/probes, links extras, and saves to database.
        Returns a tuple of (new_or_modified_items_needing_enrichment, probe_infos).
        """
        if self.progress_callback:
            self.progress_callback(5.0)

        # 1. Collect files from root_path
        files = self.collector.collect([self.library.root_path], self.db)
        potential_media = files["potential_media"]
        potential_extras = files["potential_extras"]

        total_files = len(potential_media) + len(potential_extras)
        logger.info("[scan:%s] Collected %s media candidates and %s extra candidates from %s", self.mode.value, len(potential_media), len(potential_extras), self.library.root_path)
        if total_files == 0:
            return [], {}

        # Cache existing media items in library by relative path and build hash lookup
        existing_items: Dict[str, MediaItem] = {}
        for item in self.db.query(MediaItem).filter(MediaItem.library_id == self.library.id).all():
            existing_items[item.relative_path.lower()] = item

        hash_lookup = self.duplicate_finder.build_media_hash_lookup(list(existing_items.values()))

        # Cache existing extras and build hash lookup
        existing_extras: Dict[str, ExtraFile] = {}
        for ex in self.db.query(ExtraFile).join(MediaItem).filter(MediaItem.library_id == self.library.id).all():
            existing_extras[ex.relative_path.lower()] = ex

        extra_hash_lookup = self.duplicate_finder.build_extra_hash_lookup(list(existing_extras.values()))

        # Determine relative path helper
        def get_rel_path(p: Path) -> str:
            return self.file_walker.get_rel_path(p)

        # 2. Identify media candidates needing probing
        probe_targets = []
        probe_durations = {}
        probe_infos = {}

        for p in potential_media:
            stat = p.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            rel_path = get_rel_path(p)
            
            existing = existing_items.get(rel_path.lower())
            if existing and existing.size == size and existing.mtime == mtime and existing.duration is not None:
                probe_durations[str(p)] = existing.duration
            else:
                probe_targets.append(p)

        # 3. Probe targets in parallel using thread pool
        if probe_targets:
            # Limit to 3 concurrent I/O threads to prevent disk bottleneck
            max_io_workers = min(3, os.cpu_count() or 3)
            with ThreadPoolExecutor(max_workers=max_io_workers) as executor:
                future_to_path = {executor.submit(self._probe_and_analyze_target, p): p for p in probe_targets}
                
                probed_count = 0
                import concurrent.futures
                for future in concurrent.futures.as_completed(future_to_path):
                    path = future_to_path[future]
                    path_str = str(path)
                    try:
                        res = future.result()
                        probe_infos[path_str] = res
                        info = res.get("probe_info")
                        if info:
                            probe_durations[path_str] = info.get("duration")
                        else:
                            probe_durations[path_str] = None
                        logger.info("[scan:%s] Probed %s | duration=%s | video=%s | md5=%s | oshash=%s | phash=%s", self.mode.value, path.name, probe_durations[path_str], bool(info and info.get("video_codec")), (res.get("hash_md5") or "")[:12], (res.get("hash_oshash") or "")[:12], (res.get("hash_phash") or "")[:12])
                    except Exception as exc:
                        probe_durations[path_str] = None
                        logger.warning("[scan:%s] Probe failed for %s: %s", self.mode.value, path.name, exc)
                    
                    probed_count += 1
                    if self.progress_callback:
                        pct = 5.0 + (float(probed_count) / len(probe_targets)) * 80.0
                        self.progress_callback(pct)

        # 4. Filter into media paths vs extra paths based on duration
        media_paths, extra_paths = self.file_walker.classify_paths(
            potential_media=potential_media,
            potential_extras=potential_extras,
            probe_durations=probe_durations,
            probe_infos=probe_infos,
            db=self.db
        )

        logger.info("[scan:%s] Classified %s media files and %s extras after duration filtering", self.mode.value, len(media_paths), len(extra_paths))

        # 5. Remove media items demoted to extras
        for p in extra_paths:
            rel_path = get_rel_path(p)
            existing_media = existing_items.get(rel_path.lower())
            if existing_media:
                self.db.delete(existing_media)
                existing_items.pop(rel_path.lower(), None)

        # Remove extras promoted to media
        for p in media_paths:
            rel_path = get_rel_path(p)
            if rel_path.lower() in existing_extras:
                ex = existing_extras.pop(rel_path.lower())
                self.db.delete(ex)

        # 6. Establish links
        links = self.linker.link(media_paths, extra_paths)
        logger.info("[scan:%s] Linked %s extras to parent media items", self.mode.value, len(links))

        # 7. Process and save MediaItems
        to_process, path_to_item = self.scan_persister.save_media_items(
            media_paths=media_paths,
            existing_items=existing_items,
            hash_lookup=hash_lookup,
            probe_infos=probe_infos,
            get_rel_path_fn=get_rel_path,
            progress_callback=self.progress_callback,
            probe_targets_len=len(probe_targets)
        )

        # 8. Process and save ExtraFiles
        self.scan_persister.save_extras(
            extra_paths=extra_paths,
            existing_extras=existing_extras,
            extra_hash_lookup=extra_hash_lookup,
            links=links,
            path_to_item=path_to_item,
            get_rel_path_fn=get_rel_path,
            extra_determiner=self.extra_determiner
        )

        if self.progress_callback:
            self.progress_callback(100.0)

        return to_process, probe_infos
