import os
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor

from app.shared_kernel.enums import ItemStatus, ExtraCategory, ExtraSubtype, ScanMode
from app.domains.library.models import Library, MediaItem, ExtraFile
from .collector import Collector
from .categorizer import Categorizer
from .linker import Linker
from .probe import TechnicalProber
from app.infrastructure.filesystem.fs_utils import (
    calculate_fast_hash,
    to_win_long_path,
    calculate_oshash,
    calculate_full_md5,
    calculate_full_sha256,
)
from .analyzer import Analyzer

def sanitize_parsed_info(data):
    import datetime
    if isinstance(data, dict):
        return {k: sanitize_parsed_info(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_parsed_info(v) for v in data]
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data

def _cpu_heavy_worker_count() -> int:
    logical_threads = os.cpu_count() or 4
    return max(2, min(8, int(logical_threads * 0.5)))

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
        progress_callback: Optional[callable] = None
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
        if total_files == 0:
            return [], {}

        # Cache existing media items in library by relative path and hash for fast lookup
        existing_items: Dict[str, MediaItem] = {}
        hash_lookup: Dict[str, List[MediaItem]] = {}
        for item in self.db.query(MediaItem).filter(MediaItem.library_id == self.library.id).all():
            existing_items[item.relative_path.lower()] = item
            if item.hash_md5:
                if item.hash_md5 not in hash_lookup:
                    hash_lookup[item.hash_md5] = []
                hash_lookup[item.hash_md5].append(item)

        existing_extras: Dict[str, ExtraFile] = {}
        extra_hash_lookup: Dict[str, List[ExtraFile]] = {}
        for ex in self.db.query(ExtraFile).join(MediaItem).filter(MediaItem.library_id == self.library.id).all():
            existing_extras[ex.relative_path.lower()] = ex
            if ex.file_hash:
                if ex.file_hash not in extra_hash_lookup:
                    extra_hash_lookup[ex.file_hash] = []
                extra_hash_lookup[ex.file_hash].append(ex)

        # Determine relative path helper
        def get_rel_path(p: Path) -> str:
            try:
                return os.path.relpath(str(p), self.library.root_path).replace("\\", "/")
            except ValueError:
                return str(p).replace("\\", "/")

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

        # 3. Probe targets in parallel using thread pool (runs probe + hashes + guessit concurrently)
        if probe_targets:
            from concurrent.futures import ThreadPoolExecutor
            # Limit to 3 concurrent I/O threads to prevent disk bottleneck / VLC stuttering
            max_io_workers = min(3, os.cpu_count() or 3)
            with ThreadPoolExecutor(max_workers=max_io_workers) as executor:
                future_to_path = {executor.submit(self._probe_and_analyze_target, p): p for p in probe_targets}
                
                probed_count = 0
                for future in future_to_path:
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
                    except Exception:
                        probe_durations[path_str] = None
                    
                    probed_count += 1
                    if self.progress_callback:
                        # Map progress between 10% and 40%
                        pct = 10.0 + (float(probed_count) / len(probe_targets)) * 30.0
                        self.progress_callback(pct)

        # 4. Filter into media paths vs extra paths based on duration
        media_paths = []
        extra_paths = list(potential_extras)
        limit_seconds = self.min_video_duration_minutes * 60

        for p in potential_media:
            p_str = str(p)
            duration = probe_durations.get(p_str)
            res = probe_infos.get(p_str)
            info = res.get("probe_info") if res else None
            is_audio_only = False
            if info:
                has_video = bool(info.get("video_codec"))
                has_audio = len(info.get("audio_streams") or []) > 0
                if not has_video and has_audio:
                    is_audio_only = True

            if is_audio_only or (duration is not None and duration < limit_seconds):
                extra_paths.append(p)
            else:
                media_paths.append(p)

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
        path_to_item = {}
        to_process = []

        # 7. Process and save MediaItems
        media_processed = 0
        for p in media_paths:
            stat = p.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            rel_path = get_rel_path(p)
            rel_path_lower = rel_path.lower()

            existing = existing_items.get(rel_path_lower)
            if existing and existing.size == size and existing.mtime == mtime:
                path_to_item[p] = existing
                if existing.status == ItemStatus.NEW:
                    to_process.append(existing)
            else:
                res = probe_infos.get(str(p))
                file_hash = res.get("hash_md5") if res else calculate_fast_hash(str(p))
                
                # Detect rename/move by hash from local memory cache
                moved_item = None
                if file_hash:
                    candidates = hash_lookup.get(file_hash) or []
                    for cand in candidates:
                        cand_full_path = os.path.join(self.library.root_path, cand.relative_path)
                        if not os.path.exists(to_win_long_path(cand_full_path)):
                            moved_item = cand
                            break
                
                if moved_item:
                    moved_item.relative_path = rel_path
                    moved_item.filename = p.name
                    moved_item.extension = p.suffix.lower()
                    moved_item.folder_name = p.parent.name
                    moved_item.size = size
                    moved_item.mtime = mtime
                    
                    if res:
                        moved_item.hash_md5 = res.get("hash_md5")
                        moved_item.hash_oshash = res.get("hash_oshash")
                        moved_item.hash_sha256 = res.get("hash_sha256")
                    else:
                        if self.mode.uses_scene_pipeline:
                            moved_item.hash_md5 = calculate_full_md5(str(p))
                            moved_item.hash_oshash = calculate_oshash(str(p))
                            moved_item.hash_sha256 = calculate_full_sha256(str(p))
                        else:
                            moved_item.hash_md5 = file_hash
                            moved_item.hash_oshash = calculate_oshash(str(p))
                        
                    path_to_item[p] = moved_item
                    if moved_item.status == ItemStatus.NEW:
                        to_process.append(moved_item)
                    existing_items[rel_path_lower] = moved_item
                else:
                    if existing:
                        existing.size = size
                        existing.mtime = mtime
                        if res:
                            existing.hash_md5 = res.get("hash_md5")
                            existing.hash_oshash = res.get("hash_oshash")
                            existing.hash_sha256 = res.get("hash_sha256")
                        else:
                            if self.mode.uses_scene_pipeline:
                                existing.hash_md5 = calculate_full_md5(str(p))
                                existing.hash_oshash = calculate_oshash(str(p))
                                existing.hash_sha256 = calculate_full_sha256(str(p))
                            else:
                                existing.hash_md5 = file_hash
                                existing.hash_oshash = calculate_oshash(str(p))
                        if existing.status != ItemStatus.MATCHED:
                            existing.status = ItemStatus.NEW
                        item = existing
                    else:
                        item = MediaItem(
                            library_id=self.library.id,
                            relative_path=rel_path,
                            filename=p.name,
                            extension=p.suffix.lower(),
                            folder_name=p.parent.name,
                            size=size,
                            mtime=mtime,
                            status=ItemStatus.NEW
                        )
                        if res:
                            item.hash_md5 = res.get("hash_md5")
                            item.hash_oshash = res.get("hash_oshash")
                            item.hash_sha256 = res.get("hash_sha256")
                        else:
                            if self.mode.uses_scene_pipeline:
                                item.hash_md5 = calculate_full_md5(str(p))
                                item.hash_oshash = calculate_oshash(str(p))
                                item.hash_sha256 = calculate_full_sha256(str(p))
                            else:
                                item.hash_md5 = file_hash
                                item.hash_oshash = calculate_oshash(str(p))
                        self.db.add(item)
                    
                    path_to_item[p] = item
                    to_process.append(item)

            # Store Technical Probed data and Guessit info if available
            res = probe_infos.get(str(p))
            item_entity = path_to_item[p]
            
            if item_entity:
                if res and res.get("probe_info"):
                    info = res["probe_info"]
                    item_entity.duration = info.get("duration")
                    item_entity.resolution = info.get("resolution")
                    item_entity.video_codec = info.get("video_codec")
                    item_entity.video_bitrate = info.get("video_bitrate")
                    item_entity.framerate = info.get("framerate")
                    item_entity.bit_depth = info.get("bit_depth")
                    item_entity.hdr_type = info.get("hdr_type")
                    item_entity.audio_codec = info.get("audio_codec")
                    item_entity.audio_channels = info.get("audio_channels")
                    item_entity.audio_bitrate = info.get("audio_bitrate")
                    item_entity.audio_streams = info.get("audio_streams")
                    item_entity.subtitle_streams = info.get("subtitle_streams")
                    item_entity.internal_title = info.get("internal_title")

                # Populate guessit metadata from pre-computed thread result or fallback run
                if not existing or existing.size != size or existing.mtime != mtime:
                    triple = res.get("guessit_info") if res else self.analyzer.get_triple_data(item_entity.internal_title, item_entity.filename, item_entity.folder_name)
                    item_entity.parsed_info = sanitize_parsed_info(triple)
                    
                    if triple:
                        fn_data = triple.get("fn") or {}
                        it_data = triple.get("it") or {}
                        fd_data = triple.get("fd") or {}
                        
                        title = fn_data.get("title") or it_data.get("title") or fd_data.get("title") or Path(item_entity.filename).stem
                        year = fn_data.get("year") or it_data.get("year") or fd_data.get("year")
                        season = fn_data.get("season") or it_data.get("season") or fd_data.get("season")
                        episode = fn_data.get("episode") or it_data.get("episode") or fd_data.get("episode")
                        
                        item_entity.group_hash = self.analyzer.generate_group_hash(title, year, season, episode)
                        
                        part = fn_data.get("part") or it_data.get("part") or fd_data.get("part")
                        if part is not None:
                            item_entity.part_number = part

            media_processed += 1
            if self.progress_callback:
                pct = 40.0 + (float(media_processed) / len(media_paths)) * 40.0
                self.progress_callback(pct)

        self.db.flush()

        # 8. Process and save ExtraFiles
        for p in extra_paths:
            rel_path = get_rel_path(p)
            if rel_path.lower() in existing_extras:
                continue

            category, subtype = self.categorizer.categorize(p, self.db)
            if category is None:
                continue

            # Scene profiles support sidecar metadata, images, subtitles, and audio tracks.
            if self.mode == ScanMode.SCENES and category not in (
                ExtraCategory.METADATA,
                ExtraCategory.IMAGE,
                ExtraCategory.SUBTITLE,
                ExtraCategory.AUDIO,
            ):
                continue

            parent_path = links.get(p)
            parent_item = path_to_item.get(parent_path)
            
            if parent_item:
                file_hash = calculate_fast_hash(str(p))
                lang = self.analyzer.extract_language(p.name)
                
                # Check for moved extra from memory cache
                moved_extra = None
                if file_hash:
                    candidates = extra_hash_lookup.get(file_hash) or []
                    for cand in candidates:
                        cand_full_path = os.path.join(self.library.root_path, cand.relative_path)
                        if not os.path.exists(to_win_long_path(cand_full_path)):
                            moved_extra = cand
                            break

                if moved_extra:
                    moved_extra.relative_path = rel_path
                    moved_extra.filename = p.name
                    moved_extra.extension = p.suffix.lower()
                    moved_extra.media_item_id = parent_item.id
                    moved_extra.category = category
                    moved_extra.subtype = subtype
                    moved_extra.language = lang
                else:
                    extra = ExtraFile(
                        media_item_id=parent_item.id,
                        relative_path=rel_path,
                        filename=p.name,
                        extension=p.suffix.lower(),
                        category=category,
                        subtype=subtype,
                        language=lang,
                        file_hash=file_hash
                    )
                    self.db.add(extra)

        self.db.commit()
        if self.progress_callback:
            self.progress_callback(100.0)

        return to_process, probe_infos

    def _probe_and_analyze_target(self, filepath: Path) -> Dict[str, Any]:
        """
        Runs ffprobe, extracts metadata, computes hashes, and analyzes names via Guessit in a background thread.
        """
        filepath_str = str(filepath)
        result = {
            "probe_spec": None,
            "hash_md5": None,
            "hash_oshash": None,
            "hash_sha256": None,
            "guessit_info": None,
        }
        
        # 1. Run ffprobe
        try:
            raw_data = self.prober.probe(filepath_str)
            info = self.prober.extract_info(raw_data)
            result["probe_info"] = info
        except Exception:
            pass

        # 2. Compute Hashes
        result["hash_oshash"] = calculate_oshash(filepath_str)
        if self.mode.uses_scene_pipeline:
            result["hash_md5"] = calculate_full_md5(filepath_str)
            result["hash_sha256"] = calculate_full_sha256(filepath_str)
        else:
            result["hash_md5"] = calculate_fast_hash(filepath_str)

        # 3. Analyze text with Guessit
        internal_title = None
        if result["probe_info"]:
            internal_title = result["probe_info"].get("internal_title")
            
        result["guessit_info"] = self.analyzer.get_triple_data(
            internal_title, 
            filepath.name, 
            filepath.parent.name
        )
        
        return result
