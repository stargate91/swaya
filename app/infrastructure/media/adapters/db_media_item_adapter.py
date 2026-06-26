from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import pathlib

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem, Library, ExtraFile
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.ports.media_item_port import MediaItemPort

class DbMediaItemAdapter(MediaItemPort):
    def get_local_library_map_by_external_ids(self, provider: str, external_ids: List[str]) -> Dict[str, int]:
        try:
            prov_enum = Provider(provider.lower())
        except ValueError:
            return {}

        matches = self.db.query(MetadataMatch).filter(
            MetadataMatch.provider == prov_enum,
            MetadataMatch.external_id.in_(external_ids),
            MetadataMatch.is_active == True
        ).all()
        
        local_map = {}
        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]
        for m in matches:
            item = m.media_item
            if item and item.status in lib_statuses:
                local_map[m.external_id] = item.id
        return local_map

    def update_library_item_type_or_hierarchy(self, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.domains.library.models import ExtraFile, MediaItem
        from app.domains.metadata.models import MetadataMatch
        from app.shared_kernel.enums import ItemStatus, MediaType, ExtraSubtype, MovieEdition, MediaAudioType, MediaSource
        
        is_extra = payload.get("type") == 'extra'
        main_type = payload.get("main_type")
        parent_id = payload.get("parent_id")
        subtype = payload.get("subtype")
        language = payload.get("language")
        season = payload.get("season")
        episode = payload.get("episode")
        custom_language = payload.get("custom_language")
        reset_match = bool(payload.get("reset_match"))
        media_type_arg = payload.get("media_type")
        
        custom_edition = payload.get("custom_edition")
        custom_audio_type = payload.get("custom_audio_type")
        custom_source = payload.get("custom_source")

        if is_extra:
            extra = self.db.query(ExtraFile).filter(ExtraFile.id == int(item_id)).first()
            if not extra:
                from app.shared_kernel.exceptions import NotFoundException
                raise NotFoundException("Target extra item not found")

            # Support conversion to movie/episode/scene
            if main_type in ("movie", "episode", "scene"):
                parent_media = extra.media_item
                if parent_media:
                    parsed_data = {"type": main_type}
                    if main_type == "episode":
                        parsed_data["season"] = season
                        parsed_data["episode"] = episode
                    new_item = MediaItem(
                        library_id=parent_media.library_id,
                        relative_path=extra.relative_path,
                        filename=extra.filename,
                        extension=extra.extension,
                        status=ItemStatus.NEW,
                        parsed_info=parsed_data,
                        custom_edition=MovieEdition.NONE if (custom_edition == "none" or not custom_edition) else MovieEdition(custom_edition.lower()) if custom_edition else MovieEdition.NONE,
                        custom_source=MediaSource.NONE if (custom_source == "none" or not custom_source) else MediaSource(custom_source.lower()) if custom_source else MediaSource.NONE,
                        custom_audio_type=MediaAudioType.NONE if (custom_audio_type == "none" or not custom_audio_type) else MediaAudioType(custom_audio_type.lower()) if custom_audio_type else MediaAudioType.NONE,
                    )
                    self.db.add(new_item)
                    self.db.delete(extra)
                    self.db.flush()
                    self.db.commit()
                    return {"status": "success", "item_id": item_id, "new_item_id": new_item.id, "converted": True}

            if parent_id is not None:
                extra.media_item_id = int(parent_id)
            if subtype is not None:
                try:
                    extra.subtype = ExtraSubtype(subtype.lower())
                except ValueError:
                    pass
            if language is not None:
                extra.language = language

            self.db.commit()
            return {"status": "success", "item_id": item_id, "converted": False}

        # Otherwise it is a MediaItem
        media_item_id, _ = self.resolve_ids(item_id, media_type=media_type_arg)
        item = None
        if media_item_id:
            item = self.db.query(MediaItem).filter(MediaItem.id == media_item_id).first()

        if not item:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Target media item not found")

        # Convert to extra if main_type is bonus
        if main_type == "bonus" and parent_id is not None:
            from app.shared_kernel.enums import ExtraCategory
            parent_item = self.db.query(MediaItem).filter(MediaItem.id == int(parent_id)).first()
            if parent_item:
                for extra in list(item.extras):
                    extra.media_item = parent_item
                item.extras.clear()
                self.db.flush()
            new_extra = ExtraFile(
                media_item_id=int(parent_id),
                relative_path=item.relative_path,
                filename=item.filename,
                extension=item.extension,
                category=ExtraCategory.VIDEO,
                subtype=ExtraSubtype(subtype.lower()) if (subtype and subtype != "none") else None,
                language=language
            )
            self.db.add(new_extra)
            self.db.delete(item)
            self.db.commit()
            return {"status": "success", "item_id": item_id, "converted": True}

        # Handle conversion between movie and episode
        if main_type in ("movie", "episode", "scene"):
            parsed = dict(item.parsed_info) if item.parsed_info else {}
            old_type = parsed.get("type")
            if not old_type:
                active_m = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
                if active_m:
                    old_type = active_m.media_type.value
                else:
                    fn_data = parsed.get("fn") or {}
                    it_data = parsed.get("it") or {}
                    fd_data = parsed.get("fd") or {}
                    old_type = fn_data.get("type") or it_data.get("type") or fd_data.get("type") or "movie"

            if str(old_type).lower() != main_type.lower():
                item.status = ItemStatus.NEW
                parsed["type"] = main_type
                for match in item.matches:
                    match.is_active = False
                    match.media_item_id = None
                
                if main_type == "movie":
                    parsed.pop("season", None)
                    parsed.pop("episode", None)
                    for k in ["fn", "it", "fd"]:
                        if k in parsed and isinstance(parsed[k], dict):
                            parsed[k].pop("season", None)
                            parsed[k].pop("episode", None)
                            parsed[k]["type"] = "movie"
                elif main_type == "episode":
                    for k in ["fn", "it", "fd"]:
                        if k in parsed and isinstance(parsed[k], dict):
                            parsed[k]["type"] = "episode"
            
            item.parsed_info = parsed

        # Edition, Audio Type, Source updates
        if custom_edition is not None:
            item.custom_edition = MovieEdition.NONE if (custom_edition == "none" or not custom_edition) else MovieEdition(custom_edition.lower())
        if custom_audio_type is not None:
            item.custom_audio_type = MediaAudioType.NONE if (custom_audio_type == "none" or not custom_audio_type) else MediaAudioType(custom_audio_type.lower())
        if custom_source is not None:
            item.custom_source = MediaSource.NONE if (custom_source == "none" or not custom_source) else MediaSource(custom_source.lower())

        # Season / Episode updates (when not necessarily changing main_type, but updating TV properties)
        if season is not None or episode is not None:
            parsed = dict(item.parsed_info) if item.parsed_info else {}
            if season is not None:
                parsed["season"] = season
                for k in ["fn", "it", "fd"]:
                    if k in parsed and isinstance(parsed[k], dict):
                        parsed[k]["season"] = season
            if episode is not None:
                parsed["episode"] = episode
                for k in ["fn", "it", "fd"]:
                    if k in parsed and isinstance(parsed[k], dict):
                        parsed[k]["episode"] = episode
            item.parsed_info = parsed
            self._shift_tv_episode_match_impl(item, parsed, season, episode, custom_language, reset_match)

        if reset_match:
            item.status = ItemStatus.NEW
            for match in item.matches:
                match.is_active = False
                match.media_item_id = None

        self.db.commit()
        return {"status": "success", "item_id": item_id, "converted": False}

    def _shift_tv_episode_match_impl(self, item, parsed, new_season, new_episode, custom_language, reset_match: bool):
        if reset_match:
            return
        from app.shared_kernel.enums import MediaType
        from app.domains.metadata.models import MetadataMatch
        active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
        if active_match and active_match.media_type in (MediaType.SEASON, MediaType.EPISODE, MediaType.TV):
            tv_match = None
            current = active_match
            while current:
                if current.media_type == MediaType.TV:
                    tv_match = current
                    break
                current = current.parent
                if not current and active_match.parent_id is not None:
                    current = self.db.query(MetadataMatch).filter(MetadataMatch.id == active_match.parent_id).first()
            
            if tv_match:
                try:
                    ns_num = int(new_season) if new_season is not None and str(new_season).isdigit() else (int(parsed.get("season")) if str(parsed.get("season")).isdigit() else 1)
                    ne_num = int(new_episode) if new_episode is not None and str(new_episode).isdigit() else (int(parsed.get("episode")) if str(parsed.get("episode")).isdigit() else 1)
                    
                    season_match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == tv_match.provider,
                        MetadataMatch.parent_id == tv_match.id,
                        MetadataMatch.media_type == MediaType.SEASON,
                        MetadataMatch.season_number == ns_num
                    ).first()
                    if not season_match:
                        season_match = MetadataMatch(
                            provider=tv_match.provider,
                            external_id=f"{tv_match.external_id}-s{ns_num}",
                            media_type=MediaType.SEASON,
                            season_number=ns_num,
                            parent_id=tv_match.id,
                            confidence_score=1.0,
                            is_adult=tv_match.is_adult
                        )
                        self.db.add(season_match)
                        self.db.flush()
                        
                    episode_match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == tv_match.provider,
                        MetadataMatch.parent_id == season_match.id,
                        MetadataMatch.media_type == MediaType.EPISODE,
                        MetadataMatch.episode_number == ne_num
                    ).first()
                    if not episode_match:
                        # Check if there is already an EPISODE match for this media item under the same TV show
                        episode_match = self.db.query(MetadataMatch).filter(
                            MetadataMatch.media_item_id == item.id,
                            MetadataMatch.provider == tv_match.provider,
                            MetadataMatch.external_id == tv_match.external_id,
                            MetadataMatch.media_type == MediaType.EPISODE
                        ).first()
                        
                        if episode_match:
                            episode_match.parent_id = season_match.id
                            episode_match.season_number = ns_num
                            episode_match.episode_number = ne_num
                            episode_match.is_active = True
                            episode_match.is_adult = tv_match.is_adult
                        else:
                            episode_match = MetadataMatch(
                                provider=tv_match.provider,
                                external_id=tv_match.external_id,
                                media_type=MediaType.EPISODE,
                                season_number=ns_num,
                                episode_number=ne_num,
                                parent_id=season_match.id,
                                confidence_score=1.0,
                                media_item_id=item.id,
                                is_active=True,
                                is_adult=tv_match.is_adult
                            )
                            self.db.add(episode_match)
                            self.db.flush()
                    else:
                        episode_match.media_item_id = item.id
                        episode_match.is_active = True
                        episode_match.is_adult = tv_match.is_adult
                        
                    for m in item.matches:
                        if m.id != episode_match.id:
                            m.is_active = False
                            m.media_item_id = None
                            
                    from app.infrastructure.scrapers.enrichment.mainstream_enricher import MainstreamEnricher
                    enricher = MainstreamEnricher(self.db)
                    enricher.enrich_matched_item(item, language=custom_language or "en")
                except Exception as e:
                    from app.infrastructure.media.db_media_resolver import logger
                    logger.error(f"Error shifting TV episode match: {e}")

    def bulk_update_library_items(self, item_ids: List[str], is_extra: bool, payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.domains.library.models import ExtraFile, MediaItem
        from app.shared_kernel.enums import ExtraSubtype, ExtraCategory, ItemStatus, MovieEdition, MediaAudioType, MediaSource
        
        parent_id = payload.get("parent_id")
        subtype = payload.get("subtype")
        language = payload.get("language")
        main_type = payload.get("main_type")
        season = payload.get("season")
        episode = payload.get("episode")
        reset_match = bool(payload.get("reset_match"))
        
        custom_edition = payload.get("custom_edition")
        custom_audio_type = payload.get("custom_audio_type")
        custom_source = payload.get("custom_source")

        count = 0
        for item_id in item_ids:
            if is_extra:
                extra = self.db.query(ExtraFile).filter(ExtraFile.id == int(item_id)).first()
                if extra:
                    if parent_id is not None:
                        extra.media_item_id = int(parent_id)
                    if subtype is not None:
                        try:
                            extra.subtype = ExtraSubtype(subtype.lower())
                        except ValueError:
                            pass
                    if language is not None:
                        extra.language = language

                    if main_type in ("movie", "episode", "scene"):
                        parent_media = extra.media_item
                        if parent_media:
                            parsed_data = {"type": main_type}
                            if main_type == "episode":
                                parsed_data["season"] = season
                                parsed_data["episode"] = episode
                            new_item = MediaItem(
                                library_id=parent_media.library_id,
                                relative_path=extra.relative_path,
                                filename=extra.filename,
                                extension=extra.extension,
                                status=ItemStatus.NEW,
                                parsed_info=parsed_data,
                                custom_edition=MovieEdition.NONE if (custom_edition == "none" or not custom_edition) else MovieEdition(custom_edition.lower()) if custom_edition else MovieEdition.NONE,
                                custom_source=MediaSource.NONE if (custom_source == "none" or not custom_source) else MediaSource(custom_source.lower()) if custom_source else MediaSource.NONE,
                                custom_audio_type=MediaAudioType.NONE if (custom_audio_type == "none" or not custom_audio_type) else MediaAudioType(custom_audio_type.lower()) if custom_audio_type else MediaAudioType.NONE,
                            )
                            self.db.add(new_item)
                            self.db.delete(extra)
                    count += 1
            else:
                item = self.db.query(MediaItem).filter(MediaItem.id == int(item_id)).first()
                if item:
                    if main_type == "bonus" and parent_id is not None:
                        parent_item = self.db.query(MediaItem).filter(MediaItem.id == int(parent_id)).first()
                        if parent_item:
                            for extra in list(item.extras):
                                extra.media_item = parent_item
                            item.extras.clear()
                            self.db.flush()
                        new_extra = ExtraFile(
                            media_item_id=int(parent_id),
                            relative_path=item.relative_path,
                            filename=item.filename,
                            extension=item.extension,
                            category=ExtraCategory.VIDEO,
                            subtype=ExtraSubtype(subtype.lower()) if (subtype and subtype != "none") else ExtraSubtype.OTHER,
                            language=language
                        )
                        self.db.add(new_extra)
                        self.db.delete(item)
                    else:
                        # Handle conversion between movie/episode/scene
                        if main_type in ("movie", "episode", "scene"):
                            parsed = dict(item.parsed_info) if item.parsed_info else {}
                            old_type = parsed.get("type")
                            if not old_type:
                                active_m = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
                                if active_m:
                                    old_type = active_m.media_type.value
                                else:
                                    fn_data = parsed.get("fn") or {}
                                    it_data = parsed.get("it") or {}
                                    fd_data = parsed.get("fd") or {}
                                    old_type = fn_data.get("type") or it_data.get("type") or fd_data.get("type") or "movie"

                            if str(old_type).lower() != main_type.lower():
                                item.status = ItemStatus.NEW
                                parsed["type"] = main_type
                                for match in item.matches:
                                    match.is_active = False
                                    match.media_item_id = None

                                if main_type == "movie":
                                    parsed.pop("season", None)
                                    parsed.pop("episode", None)
                                    for k in ["fn", "it", "fd"]:
                                        if k in parsed and isinstance(parsed[k], dict):
                                            parsed[k].pop("season", None)
                                            parsed[k].pop("episode", None)
                                            parsed[k]["type"] = "movie"
                                elif main_type == "episode":
                                    for k in ["fn", "it", "fd"]:
                                        if k in parsed and isinstance(parsed[k], dict):
                                            parsed[k]["type"] = "episode"

                            item.parsed_info = parsed

                        if custom_edition is not None:
                            item.custom_edition = MovieEdition.NONE if (custom_edition == "none" or not custom_edition) else MovieEdition(custom_edition.lower())
                        if custom_audio_type is not None:
                            item.custom_audio_type = MediaAudioType.NONE if (custom_audio_type == "none" or not custom_audio_type) else MediaAudioType(custom_audio_type.lower())
                        if custom_source is not None:
                            item.custom_source = MediaSource.NONE if (custom_source == "none" or not custom_source) else MediaSource(custom_source.lower())
                        
                        if season is not None or episode is not None:
                            parsed = dict(item.parsed_info) if item.parsed_info else {}
                            if season is not None:
                                parsed["season"] = season
                                for k in ["fn", "it", "fd"]:
                                    if k in parsed and isinstance(parsed[k], dict):
                                        parsed[k]["season"] = season
                            if episode is not None:
                                parsed["episode"] = episode
                                for k in ["fn", "it", "fd"]:
                                    if k in parsed and isinstance(parsed[k], dict):
                                        parsed[k]["episode"] = episode
                            item.parsed_info = parsed
                            self._shift_tv_episode_match_impl(item, parsed, season, episode, payload.get("custom_language"), reset_match)

                        if reset_match:
                            for match in item.matches:
                                match.is_active = False
                    count += 1
        
        self.db.commit()
        return {"status": "success", "count": count}

    def get_ignored_items(self, search: str = "", offset: int = 0, limit: int = 40) -> Dict[str, Any]:
        query = self.db.query(MediaItem).filter(MediaItem.status == ItemStatus.IGNORED)
        if search:
            pattern = f"%{search}%"
            query = query.filter(MediaItem.filename.ilike(pattern))
            
        total = query.count()
        items = query.order_by(MediaItem.ignored_at.desc()).offset(offset).limit(limit).all()
        
        serialized = [{
            "id": item.id,
            "filename": item.filename,
            "current_path": item.current_path,
            "item_type": item.matches[0].media_type.value if item.matches else None,
            "status": item.status.value,
            "ignored_at": item.ignored_at.isoformat() if item.ignored_at else None,
        } for item in items]
        
        return {
            "items": serialized,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(items) < total,
        }

    def restore_ignored_items(self, item_ids: List[int]) -> int:
        items = self.db.query(MediaItem).filter(MediaItem.id.in_(item_ids), MediaItem.status == ItemStatus.IGNORED).all()
        for item in items:
            item.status = item.ignored_previous_status or ItemStatus.NEW
            item.ignored_previous_status = None
            item.ignored_at = None
        self.db.commit()
        return len(items)

    def repair_inconsistent_matched_items(self) -> int:
        inconsistent_items = self.db.query(MediaItem).filter(
            MediaItem.status.in_([ItemStatus.MATCHED, ItemStatus.ORGANIZED, ItemStatus.RENAMED])
        ).all()
        repaired_count = 0
        for item in inconsistent_items:
            if not item.matches:
                item.status = ItemStatus.NEW
                repaired_count += 1
        if repaired_count > 0:
            self.db.commit()
        return repaired_count

    def get_all_libraries(self) -> List[Any]:
        from app.domains.library.models import Library
        return self.db.query(Library).all()

    def create_library(self, name: str, root_path: str) -> Any:
        from app.domains.library.models import Library
        new_lib = Library(name=name, root_path=root_path)
        self.db.add(new_lib)
        self.db.commit()
        return new_lib

    def get_item_by_id(self, item_id: int) -> Optional[Any]:
        return self.db.query(MediaItem).filter(MediaItem.id == item_id).first()

    def set_item_status(self, item_id: int, status: Any) -> None:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if item:
            item.status = status
            self.db.commit()

    def get_extra_by_id(self, extra_id: int) -> Optional[Any]:
        from app.domains.library.models import ExtraFile
        return self.db.query(ExtraFile).filter(ExtraFile.id == extra_id).first()

    def get_item_by_relative_path(self, relative_path: str) -> Optional[Any]:
        return self.db.query(MediaItem).filter(MediaItem.relative_path == relative_path).first()

    def get_item_by_absolute_path(self, absolute_path: str) -> Optional[Any]:
        target_path = pathlib.Path(absolute_path).resolve()
        for item in self.db.query(MediaItem).all():
            if pathlib.Path(item.current_path).resolve() == target_path:
                return item
        return None

    def delete_item(self, item_id: int) -> None:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if item:
            self.db.delete(item)
            self.db.flush()

    def delete_extra(self, extra_id: int) -> None:
        from app.domains.library.models import ExtraFile
        extra = self.db.query(ExtraFile).filter(ExtraFile.id == extra_id).first()
        if extra:
            self.db.delete(extra)
            self.db.flush()

    def update_item_path_and_status(self, item_id: int, path: str, status: Any) -> None:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if item:
            item.current_path = path
            item.status = status
            self.db.flush()

    def update_extra_path(self, extra_id: int, path: str) -> None:
        from app.domains.library.models import ExtraFile
        extra = self.db.query(ExtraFile).filter(ExtraFile.id == extra_id).first()
        if extra:
            extra.current_path = path
            self.db.flush()
