import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, func

from app.shared_kernel.enums import Provider, MediaType, ItemStatus, CustomListType, ActionStatus, ExtraCategory
from app.domains.users.models import User, CustomList, CustomListItem
from app.domains.library.models import MediaItem, Library, ExtraFile
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.ports.settings_port import SettingsPort
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.language import LanguageService

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.application.recommendations.schemas import (
    RecommendationsResponse,
    OrganizerGroupsResponse,
    ActionResponse,
)

logger = logging.getLogger(__name__)

class RecommendationsService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort, settings_port: Optional[SettingsPort] = None):
        self.db = db
        self.scraper = scrapers.tmdb(db)
        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
        self.settings = settings_port or DbSettingsAdapter(db)
        self.img_service = image_processing_service

    def _preferred_metadata_language(self) -> str:
        lang = self.settings.get_setting("primary_metadata_language")
        return lang if lang else DEFAULT_FALLBACK_LANGUAGE


    def _resolve_image_with_fallback(
        self,
        local_path: Optional[str],
        remote_path: Optional[str],
        subfolder: str,
    ) -> Optional[str]:
        resolved = self.img_service.resolve_image_url(local_path, subfolder)
        if resolved:
            return resolved
        return self.img_service.resolve_image_url(remote_path, subfolder)


    def _infer_organizer_type(self, item: MediaItem) -> str:
        scan_mode = str((item.parsed_info or {}).get("scan_mode") or "").lower()

        if item.matches:
            return item.matches[0].media_type.value

        gtype = None
        if item.parsed_info:
            fn_data = item.parsed_info.get("fn") or {}
            it_data = item.parsed_info.get("it") or {}
            fd_data = item.parsed_info.get("fd") or {}
            gtype = fn_data.get("type") or it_data.get("type") or fd_data.get("type")

        if gtype:
            return str(gtype).lower()

        import re
        filename = item.filename.lower()
        if re.search(r"s\d+e\d+", filename) or re.search(r"\b\d+x\d+\b", filename) or re.search(r"\b(ep|episode)\s*\d+\b", filename):
            return MediaType.EPISODE.value
        return MediaType.MOVIE.value

    def _resolve_local_recommendation_bindings(self, items: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
        movie_ids = set()
        tv_ids = set()
        for item in items or []:
            tmdb_id = item.get("id")
            if not tmdb_id:
                continue
            media_type = item.get("media_type") or ("movie" if item.get("title") else "tv")
            if media_type == "tv":
                tv_ids.add(str(tmdb_id))
            else:
                movie_ids.add(str(tmdb_id))

        if not movie_ids and not tv_ids:
            return {}

        filters = []
        if movie_ids:
            filters.append((MetadataMatch.provider == Provider.TMDB) & (MetadataMatch.external_id.in_(movie_ids)))
        if tv_ids:
            filters.append((MetadataMatch.provider == Provider.TMDB) & (MetadataMatch.external_id.in_(tv_ids)))

        rows = self.db.query(
            MediaItem.id,
            MetadataMatch.external_id,
            MetadataMatch.media_type,
            MetadataMatch.rating_tmdb,
            MetadataMatch.rating_imdb
        ).join(
            MetadataMatch, MetadataMatch.media_item_id == MediaItem.id
        ).filter(
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED]),
            or_(*filters)
        ).all()

        bindings = {}
        for r in rows:
            m_type = "tv" if r.media_type == MediaType.TV else "movie"
            bindings[(m_type, int(r.external_id))] = {
                "media_item_id": r.id,
                "rating_imdb": r.rating_imdb,
                "rating_tmdb": r.rating_tmdb,
            }
        return bindings

    def get_recommendations(self, language: Optional[str] = None) -> RecommendationsResponse:
        # 1. Fetch watchlist TMDB IDs
        watchlist = self.db.query(CustomList).filter(CustomList.name == "Watchlist").first()
        watchlist_tmdb_ids = []
        if watchlist:
            watchlist_tmdb_ids = [
                int(item.match.external_id) for item in watchlist.items
                if item.match and item.match.provider == Provider.TMDB and item.match.external_id.isdigit()
            ]

        pref_lang = language or self._preferred_metadata_language()

        # Fetch trending and popular items from TMDB via scraper API
        trending_movie = self.scraper.get_trending("movie", "day", language=pref_lang)
        trending_tv = self.scraper.get_trending("tv", "day", language=pref_lang)

        trending_results = trending_movie.get("results", [])[:10] + trending_tv.get("results", [])[:10]
        discover_movies = self.scraper.discover("movie", language=pref_lang, sort_by="popularity.desc").get("results", [])
        discover_tv = self.scraper.discover("tv", language=pref_lang, sort_by="popularity.desc").get("results", [])

        # Annotate items with library bindings
        bindings = self._resolve_local_recommendation_bindings(trending_results + discover_movies + discover_tv)

        def annotate(items):
            annotated = []
            for item in items:
                tmdb_id = item.get("id")
                media_type = item.get("media_type") or ("movie" if item.get("title") else "tv")
                bind = bindings.get((media_type, tmdb_id), {})
                annotated.append({
                    **item,
                    "media_type": media_type,
                    "in_library": bind.get("media_item_id") is not None,
                    "media_item_id": bind.get("media_item_id"),
                    "rating_imdb": bind.get("rating_imdb") or item.get("vote_average"),
                    "rating_tmdb": bind.get("rating_tmdb") or item.get("vote_average"),
                })
            return annotated

        return RecommendationsResponse(
            trending=annotate(trending_results),
            discover_movies=annotate(discover_movies),
            discover_tv=annotate(discover_tv),
            top_movie_genre="Action",
            top_tv_genre="Drama",
            watchlist_item_ids=watchlist_tmdb_ids
        )

    def get_organizer_groups(self) -> OrganizerGroupsResponse:
        # Retrieve all items needing review
        items = self.db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.extras),
            joinedload(MediaItem.overrides)
        ).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).all()

        from app.infrastructure.settings.formatter_config_adapter import build_formatter_from_db
        formatter = build_formatter_from_db(self.db)
        config = formatter.config

        groups = {"manual": [], "movies": [], "tv": [], "extras": [], "collisions": []}

        parent_planned_paths = {}
        parent_types = {}
        parent_statuses = {}
        pref_lang = self._preferred_metadata_language()

        for item in items:
            active_match = next((m for m in item.matches), None)
            planned_path = item.planned_path
            action = None

            # Determine resolved target language for this specific item (override or global config default)
            overrides = item.overrides
            target_lang = overrides.custom_language if (overrides and overrides.custom_language) else (formatter.config.default_target_language or pref_lang)

            if active_match:
                loc = LanguageService.get_best_localization(active_match.localizations, target_lang)
                if loc:
                    try:
                        preview = formatter.format_item(item, active_match, loc)
                        planned_path = str(preview.target_path).replace("\\", "/")
                        action = getattr(preview, "action", "rename")
                    except Exception:
                        pass

            parent_planned_paths[item.id] = planned_path

            matches_dto = []
            for m in item.matches:
                loc = LanguageService.get_best_localization(m.localizations, pref_lang)
                matches_dto.append({
                    "id": m.id,
                    "tmdb_id": int(m.external_id) if m.external_id.isdigit() else None,
                    "type": m.media_type.value,
                    "title": loc.title if loc else "",
                    "year": m.release_date.year if m.release_date else None,
                    "poster_path": loc.poster_path if loc else None,
                    "vote_average": m.rating_tmdb,
                    "is_active": True,
                    "confidence": m.confidence_score
                })

            itype = self._infer_organizer_type(item)

            images_list = []
            if item.matches:
                active_m = next((m for m in item.matches), None)
                if active_m:
                    if active_m.media_type == MediaType.EPISODE:
                        season_m = None
                        if active_m.parent_id:
                            season_m = self.db.query(MetadataMatch).filter(MetadataMatch.id == active_m.parent_id).first()

                        tv_m = None
                        if season_m and season_m.parent_id:
                            tv_m = self.db.query(MetadataMatch).filter(MetadataMatch.id == season_m.parent_id).first()
                        elif active_m.parent_id:
                            parent_m = self.db.query(MetadataMatch).filter(MetadataMatch.id == active_m.parent_id).first()
                            if parent_m and parent_m.media_type == MediaType.TV:
                                tv_m = parent_m

                        if season_m:
                            loc = LanguageService.get_best_localization(season_m.localizations, target_lang)
                            if loc:
                                resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                                if resolved:
                                    images_list.append({"path": resolved})

                        if tv_m:
                            loc = LanguageService.get_best_localization(tv_m.localizations, target_lang)
                            if loc:
                                resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                                if resolved:
                                    images_list.append({"path": resolved})

                        if not images_list:
                            resolved = self._resolve_image_with_fallback(active_m.local_still_path, active_m.still_path, "stills")
                            if resolved:
                                images_list.append({"path": resolved})
                    elif active_m.media_type == MediaType.SCENE:
                        resolved = self._resolve_image_with_fallback(active_m.local_backdrop_path, active_m.backdrop_path, "scene_stills")
                        if resolved:
                            images_list.append({"path": resolved})
                        else:
                            loc = LanguageService.get_best_localization(active_m.localizations, target_lang)
                            if loc:
                                resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                                if resolved:
                                    images_list.append({"path": resolved})
                    else:
                        loc = LanguageService.get_best_localization(active_m.localizations, target_lang)
                        if loc:
                            resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                            if resolved:
                                images_list.append({"path": resolved})

            parent_types[item.id] = itype
            parent_statuses[item.id] = item.status.value

            item_dto = {
                "id": item.id,
                "filename": item.filename,
                "status": item.status.value,
                "type": itype,
                "title": item.filename,
                "planned_path": planned_path,
                "extension": item.extension,
                "size_mb": round((item.size or 0) / (1024 * 1024), 2),
                "images": images_list,
                "matches": matches_dto,
                "current_path": item.current_path,
                "action": action,
                "target_language": target_lang
            }

            if item.status in [ItemStatus.NEW, ItemStatus.UNCERTAIN, ItemStatus.NO_MATCH, ItemStatus.MULTIPLE, ItemStatus.ERROR]:
                groups["manual"].append(item_dto)
            else:
                is_movie = any(m.media_type == MediaType.MOVIE for m in item.matches)
                if is_movie:
                    groups["movies"].append(item_dto)
                else:
                    groups["tv"].append(item_dto)

        # Retrieve and format extras
        extras = self.db.query(ExtraFile).join(
            MediaItem, ExtraFile.media_item_id == MediaItem.id
        ).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).all()

        for ex in extras:
            parent_p_path = parent_planned_paths.get(ex.media_item_id) or ""
            groups["extras"].append({
                "id": ex.id,
                "parent_id": ex.media_item_id,
                "parent_type": parent_types.get(ex.media_item_id, "unknown"),
                "parent_status": parent_statuses.get(ex.media_item_id),
                "parent_name": Path(parent_p_path).stem if parent_p_path else ex.media_item.filename,
                "filename": ex.filename,
                "extension": ex.extension,
                "category": ex.category.value,
                "subtype": ex.subtype.value if ex.subtype else "other",
                "language": ex.language,
                "path": ex.current_path,
                "planned_path": str(Path(parent_p_path).parent / ex.filename).replace("\\", "/"),
                "action": "rename"
            })

        return OrganizerGroupsResponse(**groups)

    def get_organizer_item_count(self) -> int:
        return self.db.query(MediaItem).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).count()

    def delete_organizer_items(self, item_ids: List[int], extra_ids: List[int], mode: str) -> ActionResponse:
        if mode == "ignore":
            items = self.db.query(MediaItem).filter(MediaItem.id.in_(item_ids)).all()
            for item in items:
                item.status = ItemStatus.IGNORED
            self.db.commit()
            return ActionResponse(status="success", ignored_items=len(item_ids))

        # Direct deletion
        if item_ids:
            self.db.query(MediaItem).filter(MediaItem.id.in_(item_ids)).delete(synchronize_session=False)
        if extra_ids:
            self.db.query(ExtraFile).filter(ExtraFile.id.in_(extra_ids)).delete(synchronize_session=False)
        self.db.commit()
        return ActionResponse(status="success", deleted_items=len(item_ids), deleted_extras=len(extra_ids), mode=mode)

    def add_to_watchlist(self, tmdb_id: int, media_type: str) -> ActionResponse:
        watchlist = self.db.query(CustomList).filter(CustomList.name == "Watchlist").first()
        if not watchlist:
            watchlist = CustomList(
                name="Watchlist",
                description="Default system watchlist.",
                list_type=CustomListType.MATCH,
                color="#3b82f6",
                icon="Bookmark"
            )
            self.db.add(watchlist)
            self.db.commit()

        # Ensure MetadataMatch placeholder
        match = self.db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tmdb_id)
        ).first()

        if not match:
            match = MetadataMatch(
                provider=Provider.TMDB,
                external_id=str(tmdb_id),
                media_type=MediaType.MOVIE if media_type == "movie" else MediaType.TV
            )
            self.db.add(match)
            self.db.commit()

        # Add to watchlist if not already there
        exists = self.db.query(CustomListItem).filter(
            CustomListItem.list_id == watchlist.id,
            CustomListItem.match_id == match.id
        ).first()

        if not exists:
            item = CustomListItem(list_id=watchlist.id, match_id=match.id)
            self.db.add(item)
            self.db.commit()
            return ActionResponse(status="success", id=item.id)

        return ActionResponse(status="success", message="Already in watchlist")

    def remove_from_watchlist(self, tmdb_id: int) -> ActionResponse:
        watchlist = self.db.query(CustomList).filter(CustomList.name == "Watchlist").first()
        if not watchlist:
            return ActionResponse(status="error", message="Watchlist not found")

        match = self.db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tmdb_id)
        ).first()

        if match:
            self.db.query(CustomListItem).filter(
                CustomListItem.list_id == watchlist.id,
                CustomListItem.match_id == match.id
            ).delete()
            self.db.commit()
            return ActionResponse(status="success")

        return ActionResponse(status="error", message="Item not found in watchlist")

