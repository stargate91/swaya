import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

from app.shared_kernel.enums import ItemStatus, ScanMode
from app.domains.library.models import Library, MediaItem, ExtraFile

logger = logging.getLogger(__name__)

def sanitize_parsed_info(data):
    import datetime
    if isinstance(data, dict):
        return {k: sanitize_parsed_info(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_parsed_info(v) for v in data]
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    return data

class ScanPersister:
    def __init__(self, db: Any, library: Library, mode: ScanMode, hash_calculator: Any, duplicate_finder: Any, analyzer: Any):
        self.db = db
        self.library = library
        self.mode = mode
        self.hash_calculator = hash_calculator
        self.duplicate_finder = duplicate_finder
        self.analyzer = analyzer

    def save_media_items(
        self,
        media_paths: List[Path],
        existing_items: Dict[str, MediaItem],
        hash_lookup: Dict[str, MediaItem],
        probe_infos: Dict[str, Dict[str, Any]],
        get_rel_path_fn: Any,
        progress_callback: Any,
        probe_targets_len: int
    ) -> Tuple[List[MediaItem], Dict[Path, MediaItem]]:
        path_to_item = {}
        to_process = []
        media_processed = 0

        for p in media_paths:
            stat = p.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            rel_path = get_rel_path_fn(p)
            rel_path_lower = rel_path.lower()

            existing = existing_items.get(rel_path_lower)
            if existing and existing.size == size and existing.mtime == mtime:
                path_to_item[p] = existing
                if existing.status == ItemStatus.NEW:
                    to_process.append(existing)
            else:
                res = probe_infos.get(str(p))
                file_hash = res.get("hash_md5") if res else self.hash_calculator.calculate_fast_hash(str(p))
                
                # Detect rename/move by hash from local memory cache
                moved_item = self.duplicate_finder.find_moved_media_item(file_hash, hash_lookup)
                
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
                        moved_item.hash_phash = res.get("hash_phash")
                        moved_item.hash_sha256 = res.get("hash_sha256")
                    else:
                        if self.mode == ScanMode.SCENES:
                            moved_item.hash_md5 = None
                            moved_item.hash_oshash = self.hash_calculator.calculate_oshash(str(p))
                            moved_item.hash_phash = self.hash_calculator.calculate_phash(str(p))
                            moved_item.hash_sha256 = None
                        else:
                            moved_item.hash_md5 = file_hash
                            moved_item.hash_oshash = self.hash_calculator.calculate_oshash(str(p))
                        
                    logger.info("[scan:%s] Re-linked moved media item %s -> %s", self.mode.value, p.name, rel_path)
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
                            existing.hash_phash = res.get("hash_phash")
                            existing.hash_sha256 = res.get("hash_sha256")
                        else:
                            if self.mode == ScanMode.SCENES:
                                existing.hash_md5 = None
                                existing.hash_oshash = self.hash_calculator.calculate_oshash(str(p))
                                existing.hash_phash = self.hash_calculator.calculate_phash(str(p))
                                existing.hash_sha256 = None
                            else:
                                existing.hash_md5 = file_hash
                                existing.hash_oshash = self.hash_calculator.calculate_oshash(str(p))
                        if existing.status not in (ItemStatus.MATCHED, ItemStatus.ORGANIZED, ItemStatus.RENAMED):
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
                            item.hash_phash = res.get("hash_phash")
                            item.hash_sha256 = res.get("hash_sha256")
                        else:
                            if self.mode == ScanMode.SCENES:
                                item.hash_md5 = None
                                item.hash_oshash = self.hash_calculator.calculate_oshash(str(p))
                                item.hash_phash = self.hash_calculator.calculate_phash(str(p))
                                item.hash_sha256 = None
                            else:
                                item.hash_md5 = file_hash
                                item.hash_oshash = self.hash_calculator.calculate_oshash(str(p))
                        self.db.add(item)
                        logger.info("[scan:%s] Created media item %s | rel=%s | md5=%s | oshash=%s | phash=%s", self.mode.value, p.name, rel_path, (item.hash_md5 or "")[:12], (item.hash_oshash or "")[:12], (item.hash_phash or "")[:12])
                    
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
                    triple = {**(triple or {}), "scan_mode": self.mode.value}
                    if self.mode in (ScanMode.SCENES, ScanMode.PORNDB_MOVIE):
                        for pk in ["fn", "it", "fd"]:
                            if pk in triple and isinstance(triple[pk], dict):
                                triple[pk].pop("season", None)
                                triple[pk].pop("episode", None)
                                triple[pk].pop("season_count", None)
                                triple[pk].pop("episode_count", None)
                                triple[pk]["type"] = "movie" if self.mode == ScanMode.PORNDB_MOVIE else "scene"
                    item_entity.parsed_info = sanitize_parsed_info(triple)
                    logger.info("[scan:%s] Parsed %s | fn.type=%s | fd.type=%s | scan_mode=%s", self.mode.value, item_entity.filename, (triple.get("fn") or {}).get("type") if triple else None, (triple.get("fd") or {}).get("type") if triple else None, triple.get("scan_mode") if triple else None)
                    
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
            if progress_callback:
                if probe_targets_len > 0:
                    pct = 85.0 + (float(media_processed) / len(media_paths)) * 13.0
                else:
                    pct = 5.0 + (float(media_processed) / len(media_paths)) * 93.0
                progress_callback(pct)

        self.db.flush()
        return to_process, path_to_item

    def save_extras(
        self,
        extra_paths: List[Path],
        existing_extras: Dict[str, ExtraFile],
        extra_hash_lookup: Dict[str, ExtraFile],
        links: Dict[Path, Path],
        path_to_item: Dict[Path, MediaItem],
        get_rel_path_fn: Any,
        extra_determiner: Any
    ):
        for p in extra_paths:
            rel_path = get_rel_path_fn(p)
            if rel_path.lower() in existing_extras:
                continue

            category, subtype = extra_determiner.determine_extra(p, self.db)
            if category is None:
                logger.info("[scan:%s] Ignored extra candidate %s because no category matched/allowed", self.mode.value, p.name)
                continue

            parent_path = links.get(p)
            parent_item = path_to_item.get(parent_path)
            
            if not parent_item:
                logger.info("[scan:%s] Extra %s had no linked parent media item", self.mode.value, p.name)

            if parent_item:
                file_hash = self.hash_calculator.calculate_fast_hash(str(p))
                lang = self.analyzer.extract_language(p.name)
                
                # Check for moved extra from memory cache
                moved_extra = self.duplicate_finder.find_moved_extra(file_hash, extra_hash_lookup)

                if moved_extra:
                    logger.info("[scan:%s] Re-linked moved extra %s -> parent %s", self.mode.value, p.name, parent_item.filename)
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
                    logger.info("[scan:%s] Added extra %s | category=%s | subtype=%s | parent=%s", self.mode.value, p.name, category.value if category else None, subtype.value if subtype else None, parent_item.filename)
        
        self.db.commit()
