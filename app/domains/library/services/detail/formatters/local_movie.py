import logging
from typing import Any
from sqlalchemy.orm import joinedload
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MediaCollection
from app.domains.people.models import Person, MediaPersonLink
from app.domains.users.models import UserOverride
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService
from app.shared_kernel.genre_utils import split_genres as _split_genres
from app.application.library.schemas import MovieDetailResponse
from app.domains.library.services.detail.formatters.base import MovieDetailFormatter

logger = logging.getLogger(__name__)

class LocalMovieFormatter(MovieDetailFormatter):
    def format(self, item_id: Any, db: Any, scrapers: Any, current_uid: Any) -> Any:
        try:
            item_id_int = int(item_id)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid item ID"})
        
        item = db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.matches).joinedload(MetadataMatch.studios),
            joinedload(MediaItem.matches).joinedload(MetadataMatch.collection).joinedload(MediaCollection.localizations),
            joinedload(MediaItem.extras),
            joinedload(MediaItem.playback_logs),
            joinedload(MediaItem.overrides),
        ).filter(MediaItem.id == item_id_int).first()
        
        if not item:
            return JSONResponse(status_code=404, content={"error": "Item not found"})
        
        active_match = next((m for m in item.matches if m.media_item_id == item.id and m.is_active), None)
        if not active_match:
            active_match = next((m for m in item.matches if m.media_item_id == item.id), None)
        if not active_match and item.matches:
            active_match = item.matches[0]
            
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        loc = LanguageService.get_best_localization(active_match.localizations, ui_lang) if active_match else None
        
        cast = []
        directors = []
        writers = []
        
        def calculate_age_at_release(birthday_str: str, release_date_str: str) -> Any:
            if not birthday_str or not release_date_str:
                return None
            try:
                from datetime import datetime
                b_date = datetime.strptime(birthday_str[:10], "%Y-%m-%d")
                r_date = datetime.strptime(release_date_str[:10], "%Y-%m-%d")
                age = r_date.year - b_date.year
                if (r_date.month, r_date.day) < (b_date.month, b_date.day):
                    age -= 1
                return age
            except:
                return None

        if active_match:
            people_links = db.query(MediaPersonLink).options(
                joinedload(MediaPersonLink.person).joinedload(Person.localizations)
            ).filter(MediaPersonLink.match_id == active_match.id).all()
            
            local_person_ids = [link.person.id for link in people_links if link.person]
            overrides = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.person_id.in_(local_person_ids)
            ).all() if local_person_ids else []
            override_map = {ov.person_id: ov.custom_poster for ov in overrides if ov.custom_poster}
            release_date_str = active_match.release_date.strftime("%Y-%m-%d") if active_match.release_date else None

            missing_birthday_ids = [link.person.id for link in people_links if link.person and link.person.birthday is None]
            if missing_birthday_ids:
                try:
                    from app.domains.tasks import task_manager
                    if task_manager.people_enrich_worker:
                        task_manager.people_enrich_worker.enqueue_people(missing_birthday_ids)
                except Exception as ex:
                    logger.error(f"Failed to auto-enqueue missing birthdays in local movie: {ex}")

            for link in sorted(people_links, key=lambda x: x.order):
                person = link.person
                custom_img = override_map.get(person.id)
                person_data = {
                    "id": person.id,
                    "name": person.name,
                    "character": link.character_name,
                    "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                    "profile_path": self._resolve_img(custom_img or person.local_profile_path or person.profile_path, "people"),
                    "popularity": (
                        person.rating_porndb
                        if person.is_adult and person.rating_porndb is not None
                        else person.popularity or 0
                    ),
                    "scene_count": person.scene_count,
                    "rating_porndb": person.rating_porndb,
                    "gender": person.gender,
                    "age_at_release": calculate_age_at_release(person.birthday, release_date_str)
                }
                if person_data["job"].lower() == "director":
                    directors.append(person_data)
                elif person_data["job"].lower() == "writer":
                    writers.append(person_data)
                elif person_data["job"].lower() == "actor":
                    cast.append(person_data)
        
        technical = {
            "resolution": item.resolution,
            "video_codec": item.video_codec,
            "audio_codec": item.audio_codec,
            "audio_channels": item.audio_channels,
            "hdr_type": item.hdr_type,
            "bit_depth": item.bit_depth,
            "framerate": item.framerate,
            "duration": item.duration,
            "size_bytes": item.size,
            "source": item.source.value if hasattr(item.source, "value") else str(item.source),
            "edition": item.edition.value if hasattr(item.edition, "value") else str(item.edition),
            "audio_type": item.audio_type.value if hasattr(item.audio_type, "value") else str(item.audio_type),
        }
        
        metadata_override = None
        if active_match:
            metadata_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.metadata_match_id == active_match.id
            ).first()

        physical_override = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            UserOverride.media_item_id == item.id
        ).first()

        override = metadata_override or item.overrides or physical_override
            
        title = (override.custom_title if (override and override.custom_title) else None) or (loc.title if loc else item.filename)
        overview = (override.custom_overview if (override and override.custom_overview) else None) or (loc.overview if loc else None)
        
        collection_data = None
        if active_match and active_match.collection:
            col = active_match.collection
            col_loc = LanguageService.get_best_localization(col.localizations, ui_lang) if col.localizations else None
            collection_data = {
                "tmdb_id": int(col.external_id) if col.external_id.isdigit() else col.id,
                "title": col_loc.title if col_loc else "Collection",
                "poster_path": self._resolve_img(col_loc.local_poster_path or col_loc.poster_path if col_loc else None, "posters"),
                "backdrop_path": self._resolve_img(col.local_backdrop_path or col.backdrop_path, "backdrops"),
            }

        keywords_list = []
        if active_match and active_match.raw_metadata:
            raw_kws = active_match.raw_metadata.get("keywords", {})
            if isinstance(raw_kws, dict):
                keywords_list = [k["name"] for k in raw_kws.get("keywords", []) if isinstance(k, dict) and "name" in k]
        
        # Fallback if raw_metadata doesn't have keywords but we have a TMDB match
        tmdb_scraper = scrapers.tmdb(db)
        if not keywords_list and active_match and active_match.provider == Provider.TMDB and active_match.external_id:
            try:
                tmdb_id_int = int(active_match.external_id)
                tmdb_data = tmdb_scraper.get_details(tmdb_id_int, "movie", language=ui_lang)
                if tmdb_data and tmdb_data.get("keywords"):
                    keywords_list = [k["name"] for k in tmdb_data.get("keywords", {}).get("keywords", [])]
            except Exception as e:
                logger.error(f"Failed to fetch live keywords fallback: {e}")

        # Extract trailer key
        trailer_key = None
        if loc and loc.trailer_url:
            url_str = loc.trailer_url
            if "watch?v=" in url_str:
                trailer_key = url_str.split("watch?v=")[1].split("&")[0]
            elif "youtu.be/" in url_str:
                trailer_key = url_str.split("youtu.be/")[1].split("?")[0]
        
        if not trailer_key and active_match and active_match.raw_metadata:
            raw_videos = active_match.raw_metadata.get("videos", {}).get("results", [])
            youtube_trailers = [v for v in raw_videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
            if not youtube_trailers:
                youtube_trailers = [v for v in raw_videos if v.get("site") == "YouTube" and v.get("key")]
            if youtube_trailers:
                trailer_key = youtube_trailers[0].get("key")

        if not trailer_key and active_match and active_match.provider == Provider.TMDB and active_match.external_id:
            try:
                tmdb_id_int = int(active_match.external_id)
                tmdb_data = tmdb_scraper.get_details(tmdb_id_int, "movie", language=ui_lang)
                if tmdb_data:
                    videos = (tmdb_data.get("videos") or {}).get("results") or []
                    youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
                    if not youtube_trailers:
                        youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
                    if youtube_trailers:
                        trailer_key = youtube_trailers[0].get("key")
            except Exception as e:
                logger.error(f"Failed to fetch live trailer fallback: {e}")

        extras_list = [
            {
                "id": ex.id,
                "name": ex.filename,
                "path": ex.current_path,
                "category": ex.category.value if hasattr(ex.category, "value") else str(ex.category),
                "subtype": ex.subtype.value if (ex.subtype and hasattr(ex.subtype, "value")) else (str(ex.subtype) if ex.subtype else None),
                "language": ex.language,
            }
            for ex in item.extras
        ] if item.extras else []

        # Merge watch properties
        is_watched = False
        watch_count = 0
        resume_position = 0
        last_watched_at_dt = None

        if metadata_override:
            is_watched = metadata_override.is_watched
            watch_count = metadata_override.watch_count or 0
            last_watched_at_dt = metadata_override.last_watched_at
        elif override:
            is_watched = override.is_watched
            watch_count = override.watch_count or 0
            last_watched_at_dt = override.last_watched_at

        if physical_override:
            if physical_override.is_watched:
                is_watched = True
            if physical_override.watch_count and physical_override.watch_count > watch_count:
                watch_count = physical_override.watch_count
            if physical_override.resume_position:
                resume_position = physical_override.resume_position
            if physical_override.last_watched_at:
                if not last_watched_at_dt or physical_override.last_watched_at > last_watched_at_dt:
                    last_watched_at_dt = physical_override.last_watched_at

        playback_logs = [
            {
                "id": log.id,
                "watched_at": log.watched_at.isoformat()
            }
            for log in sorted(item.playback_logs or [], key=lambda x: x.watched_at, reverse=True)
        ]

        result = {
            "id": item.id,
            "title": title,
            "keywords": keywords_list,
            "trailer_key": trailer_key,
            "extras": extras_list,
            "logo_path": self._resolve_img(override.custom_logo if (override and override.custom_logo) else (loc.logo_path if loc else None), "logos"),
            "original_title": active_match.original_title if active_match else None,
            "tagline": loc.tagline if loc else None,
            "overview": overview,
            "genres": _split_genres(loc.genres) if (loc and loc.genres) else [],
            "year": active_match.release_date.year if (active_match and active_match.release_date) else None,
            "release_date": active_match.release_date.isoformat() if (active_match and active_match.release_date) else None,
            "runtime": active_match.runtime if active_match else None,
            "rating_tmdb": active_match.rating_tmdb if (active_match and active_match.rating_tmdb is not None) else None,
            "rating_imdb": active_match.rating_imdb if active_match else None,
            "rating_rotten": active_match.rating_rotten if active_match else None,
            "rating_meta": active_match.rating_meta if active_match else None,
            "rating_porndb": active_match.rating_porndb if active_match else None,
            "vote_count_tmdb": active_match.vote_count_tmdb if (active_match and active_match.vote_count_tmdb is not None) else None,
            "budget": active_match.budget if active_match else None,
            "revenue": active_match.revenue if active_match else None,
            "companies": [{"name": s.name, "logo_path": self._resolve_img(s.logo_path, "logos")} for s in active_match.studios] if active_match else [],
            "networks": [],
            "poster_path": self._resolve_img(override.custom_poster if (override and override.custom_poster) else (loc.poster_path if loc else None), "posters"),
            "backdrop_path": self._resolve_img(override.custom_backdrop if (override and override.custom_backdrop) else (active_match.backdrop_path if active_match else None), "backdrops", size="original"),
            "original_language": loc.original_language if loc else DEFAULT_FALLBACK_LANGUAGE,
            "type": active_match.media_type.value if active_match else "movie",
            "tmdb_id": int(active_match.external_id) if (active_match and active_match.provider == Provider.TMDB and active_match.external_id.isdigit()) else None,
            "imdb_id": active_match.imdb_id if active_match else None,
            "collection_data": collection_data,
            "cast": cast,
            "cast_total": len(cast),
            "people_complete": True,
            "directors": directors,
            "writers": writers,
            "is_adult": active_match.is_adult if active_match else False,
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "custom_tags": [t.name for t in override.tags if t.is_adult == bool(active_match.is_adult if active_match else False)] if (override and override.tags) else [],
            "suggested_tags": active_match.suggested_tags if (active_match and active_match.suggested_tags) else [],
            "technical": technical,
            "in_library": True,
            "path": item.current_path,
            "filename": item.filename,
            "watch_count": watch_count,
            "is_watched": is_watched,
            "resume_position": resume_position,
            "last_watched_at": last_watched_at_dt.isoformat() if last_watched_at_dt else None,
            "playback_logs": playback_logs,
        }
        
        ext_ids = {}
        if active_match:
            p_val = active_match.provider.value if hasattr(active_match.provider, "value") else str(active_match.provider)
            p_val = p_val.lower()
            if p_val == "tmdb":
                ext_ids["tmdb"] = active_match.external_id
            elif p_val in ("porndb", "theporndb"):
                ext_ids["porndb_id"] = active_match.external_id
                ext_ids["source"] = "porndb"
            elif p_val == "fansdb":
                ext_ids["fansdb_id"] = active_match.external_id
                ext_ids["source"] = "fansdb"
            elif p_val in ("stash", "stashdb"):
                ext_ids["stash_id"] = active_match.external_id
                ext_ids["source"] = "stash"
            if active_match.imdb_id:
                ext_ids["imdb"] = active_match.imdb_id

        from app.domains.library.services.detail.external_links import generate_external_links
        media_type_val = result["type"]
        result["external_links"] = generate_external_links(ext_ids, media_type_val)
        return MovieDetailResponse(**result)
