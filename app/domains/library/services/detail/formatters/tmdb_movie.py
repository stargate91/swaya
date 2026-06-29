import logging
from typing import Any
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType
from app.domains.users.models import UserOverride
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService
from app.shared_kernel.genre_utils import split_genres as _split_genres
from app.application.library.schemas import MovieDetailResponse
from app.domains.library.services.detail.formatters.base import MovieDetailFormatter

logger = logging.getLogger(__name__)

class TmdbMovieFormatter(MovieDetailFormatter):
    def format(self, item_id: Any, db: Any, scrapers: Any, current_uid: Any) -> Any:
        try:
            tmdb_id = int(item_id.split("_")[1])
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid TMDB ID format"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        tmdb_scraper = scrapers.tmdb(db)
        tmdb_data = tmdb_scraper.get_details(tmdb_id, "movie", language=ui_lang)
        if not tmdb_data:
            return JSONResponse(status_code=404, content={"error": "Movie not found on TMDB"})
        
        credits = tmdb_data.get("credits", {})
        from app.domains.people.models import Person

        # Fetch local overrides for matching TMDB people
        person_ids = set()
        for actor in credits.get("cast", []):
            if actor.get("id"):
                person_ids.add(str(actor["id"]))
        for crew in credits.get("crew", []):
            if crew.get("id"):
                person_ids.add(str(crew["id"]))

        local_profiles = {}
        if person_ids:
            try:
                from sqlalchemy import or_
                from app.domains.users.models import UserOverride
                quoted_pids = [f'"{pid}"' for pid in person_ids]
                raw_pids = list(person_ids)
                local_people = db.query(Person).filter(
                    or_(
                        Person.external_ids["tmdb"].as_string().in_(raw_pids),
                        Person.external_ids["tmdb"].as_string().in_(quoted_pids)
                    )
                ).all()
                
                local_person_ids = [lp.id for lp in local_people]
                overrides = db.query(UserOverride).filter(
                    UserOverride.user_id == current_uid,
                    UserOverride.person_id.in_(local_person_ids)
                ).all()
                override_map = {ov.person_id: ov.custom_poster for ov in overrides if ov.custom_poster}

                for lp in local_people:
                    tmdb_id_str = lp.external_ids.get("tmdb")
                    if tmdb_id_str:
                        custom_img = override_map.get(lp.id)
                        local_profiles[int(tmdb_id_str)] = {
                            "profile_path": custom_img or lp.local_profile_path or lp.profile_path,
                            "birthday": lp.birthday
                        }
                
                missing_birthday_ids = [lp.id for lp in local_people if lp.birthday is None]
                if missing_birthday_ids:
                    try:
                        from app.domains.tasks import task_manager
                        if task_manager.people_enrich_worker:
                            task_manager.people_enrich_worker.enqueue_people(missing_birthday_ids)
                    except Exception as ex:
                        logger.error(f"Failed to auto-enqueue missing birthdays: {ex}")
            except Exception as e:
                logger.error(f"Failed to query custom performer avatars for movie detail: {e}")

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

        release_date = tmdb_data.get("release_date")

        cast = []
        directors = []
        writers = []
        sound = []
        
        for actor in credits.get("cast", [])[:15]:
            actor_id = actor.get("id")
            resolved = local_profiles.get(actor_id) if actor_id else None
            resolved_img = resolved.get("profile_path") if resolved else None
            birthday_str = resolved.get("birthday") if resolved else None
            cast.append({
                "id": f"tmdb:{actor_id}" if actor_id else None,
                "name": actor.get("name"),
                "character": actor.get("character"),
                "job": "Actor",
                "profile_path": self._resolve_img(resolved_img or actor.get("profile_path"), "people"),
                "popularity": actor.get("popularity", 0),
                "gender": actor.get("gender"),
                "age_at_release": calculate_age_at_release(birthday_str, release_date)
            })
        
        for crew in credits.get("crew", []):
            crew_id = crew.get("id")
            resolved = local_profiles.get(crew_id) if crew_id else None
            resolved_img = resolved.get("profile_path") if resolved else None
            birthday_str = resolved.get("birthday") if resolved else None
            crew_member = {
                "id": f"tmdb:{crew_id}" if crew_id else None,
                "name": crew.get("name"),
                "job": crew.get("job"),
                "profile_path": self._resolve_img(resolved_img or crew.get("profile_path"), "people"),
                "popularity": crew.get("popularity", 0),
                "gender": crew.get("gender"),
                "age_at_release": calculate_age_at_release(birthday_str, release_date)
            }
            if crew.get("job") == "Director":
                directors.append(crew_member)
            elif crew.get("job") in ("Writer", "Screenplay"):
                writers.append(crew_member)
            elif crew.get("department") == "Sound" or crew.get("job") in ("Original Music Composer", "Music", "Composer"):
                sound.append(crew_member)
        year = None
        if release_date:
            try:
                year = int(release_date.split("-")[0])
            except:
                pass
        
        metadata_override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
            UserOverride.user_id == current_uid,
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tmdb_id),
            MetadataMatch.media_type == MediaType.MOVIE
        ).first()
        
        match = db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tmdb_id),
            MetadataMatch.media_type == MediaType.MOVIE
        ).first()
        
        physical_override = None
        if match and match.media_item_id:
            physical_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.media_item_id == match.media_item_id
            ).first()

        override = metadata_override
        
        from app.domains.media_assets.services.images import image_processing_service
        effective_backdrop = None
        if override and override.custom_backdrop:
            effective_backdrop = override.custom_backdrop
        else:
            effective_backdrop = image_processing_service.pick_backdrop_path(tmdb_data, preferred_language=ui_lang, allow_low_res=True)

        effective_logo = None
        if override and override.custom_logo:
            effective_logo = override.custom_logo
        else:
            effective_logo = image_processing_service.pick_logo_path(tmdb_data, preferred_language=ui_lang)

        if match:
            db_updated = False
            if not match.backdrop_path and effective_backdrop:
                match.backdrop_path = effective_backdrop
                db_updated = True
            if not match.release_date and release_date:
                from datetime import datetime
                try:
                    match.release_date = datetime.strptime(release_date, "%Y-%m-%d")
                    db_updated = True
                except:
                    pass
            if not match.rating_tmdb and tmdb_data.get("vote_average"):
                try:
                    match.rating_tmdb = float(tmdb_data.get("vote_average"))
                    db_updated = True
                except:
                    pass
            if not match.vote_count_tmdb and tmdb_data.get("vote_count"):
                try:
                    match.vote_count_tmdb = int(tmdb_data.get("vote_count"))
                    db_updated = True
                except:
                    pass
            if match.is_adult != tmdb_data.get("adult", False):
                match.is_adult = tmdb_data.get("adult", False)
                db_updated = True
            
            loc_db = next((l for l in match.localizations if l.locale == ui_lang), None)
            if not loc_db:
                from app.domains.metadata.models import MetadataLocalization
                loc_db = MetadataLocalization(
                    match_id=match.id,
                    locale=ui_lang,
                    title=tmdb_data.get("title") or tmdb_data.get("original_title") or "Unknown Movie",
                    overview=tmdb_data.get("overview"),
                    poster_path=tmdb_data.get("poster_path")
                )
                db.add(loc_db)
                db_updated = True
            else:
                if not loc_db.title and (tmdb_data.get("title") or tmdb_data.get("original_title")):
                    loc_db.title = tmdb_data.get("title") or tmdb_data.get("original_title")
                    db_updated = True
                if not loc_db.overview and tmdb_data.get("overview"):
                    loc_db.overview = tmdb_data.get("overview")
                    db_updated = True
                if not loc_db.poster_path and tmdb_data.get("poster_path"):
                    loc_db.poster_path = tmdb_data.get("poster_path")
                    db_updated = True
            
            if db_updated:
                db.commit()

        belongs_to_col = tmdb_data.get("belongs_to_collection")
        collection_data = None
        if belongs_to_col:
            col_db = match.collection if (match and match.collection and match.collection.external_id == str(belongs_to_col.get("id"))) else None
            col_loc = LanguageService.get_best_localization(col_db.localizations, ui_lang) if (col_db and col_db.localizations) else None
            collection_data = {
                "tmdb_id": belongs_to_col.get("id"),
                "title": belongs_to_col.get("name"),
                "poster_path": self._resolve_img(col_loc.local_poster_path or col_loc.poster_path if col_loc else belongs_to_col.get("poster_path"), "posters"),
                "backdrop_path": self._resolve_img(col_db.local_backdrop_path or col_db.backdrop_path if col_db else belongs_to_col.get("backdrop_path"), "backdrops"),
            }

        keywords_list = [k["name"] for k in tmdb_data.get("keywords", {}).get("keywords", [])] if tmdb_data.get("keywords") else []

        videos = (tmdb_data.get("videos") or {}).get("results") or []
        trailer_key = None
        youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
        if not youtube_trailers:
            youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
        if youtube_trailers:
            trailer_key = youtube_trailers[0].get("key")

        # Merge watch properties
        is_watched = False
        watch_count = 0
        resume_position = 0
        last_watched_at_dt = None

        if metadata_override:
            is_watched = metadata_override.is_watched
            watch_count = metadata_override.watch_count or 0
            last_watched_at_dt = metadata_override.last_watched_at

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

        playback_logs = []
        if match and match.media_item_id:
            from app.domains.history.models import PlaybackLog
            logs = db.query(PlaybackLog).filter(
                PlaybackLog.user_id == current_uid,
                PlaybackLog.media_item_id == match.media_item_id
            ).order_by(PlaybackLog.watched_at.desc()).all()
            playback_logs = [
                {
                    "id": log.id,
                    "watched_at": log.watched_at.isoformat()
                }
                for log in logs
            ]

        result = {
            "id": f"tmdb_{tmdb_id}",
            "title": tmdb_data.get("title") or tmdb_data.get("original_title") or "Unknown",
            "keywords": keywords_list,
            "trailer_key": trailer_key,
            "logo_path": self._resolve_img(effective_logo, "logos"),
            "original_title": tmdb_data.get("original_title"),
            "tagline": tmdb_data.get("tagline"),
            "overview": tmdb_data.get("overview"),
            "genres": _split_genres([g["name"] for g in tmdb_data.get("genres", [])]) if tmdb_data.get("genres") else [],
            "year": year,
            "release_date": release_date,
            "runtime": tmdb_data.get("runtime"),
            "rating_tmdb": tmdb_data.get("vote_average"),
            "rating_imdb": match.rating_imdb if match else None,
            "rating_rotten": match.rating_rotten if match else None,
            "rating_meta": match.rating_meta if match else None,
            "vote_count_tmdb": tmdb_data.get("vote_count"),
            "budget": tmdb_data.get("budget") or (match.budget if match else None),
            "revenue": tmdb_data.get("revenue") or (match.revenue if match else None),
            "companies": [{"name": c.get("name"), "logo_path": self._resolve_img(c.get("logo_path"), "logos")} for c in tmdb_data.get("production_companies", [])] if tmdb_data.get("production_companies") else [],
            "networks": [],
            "poster_path": self._resolve_img(override.custom_poster if (override and override.custom_poster) else tmdb_data.get("poster_path"), "posters"),
            "backdrop_path": self._resolve_img(effective_backdrop, "backdrops", size="original"),
            "original_language": tmdb_data.get("original_language"),
            "type": "movie",
            "tmdb_id": tmdb_id,
            "collection_data": collection_data,
            "cast": cast,
            "cast_total": len(credits.get("cast", [])),
            "people_complete": True,
            "directors": directors,
            "writers": writers,
            "sound": sound,
            "is_adult": tmdb_data.get("adult", False),
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "custom_tags": [t.name for t in override.tags if t.is_adult == bool(tmdb_data.get("adult", False))] if (override and override.tags) else [],
            "suggested_tags": [k["name"] for k in tmdb_data.get("keywords", {}).get("keywords", [])] if tmdb_data.get("keywords") else [],
            "tags": [],
            "is_tracked": override.is_tracked if override else False,
            "watch_count": watch_count,
            "is_watched": is_watched,
            "resume_position": resume_position,
            "last_watched_at": last_watched_at_dt.isoformat() if last_watched_at_dt else None,
            "playback_logs": playback_logs,
            "in_library": match is not None and match.media_item_id is not None,
            "library_item_id": match.media_item_id if (match and match.media_item_id) else None,
        }
        
        peaks_count = 0
        peaks_history = []
        if match and match.media_item_id:
            from app.domains.history.models import PlaybackPeakLog
            peaks = db.query(PlaybackPeakLog).filter(
                PlaybackPeakLog.user_id == current_uid,
                PlaybackPeakLog.media_item_id == match.media_item_id
            ).order_by(PlaybackPeakLog.video_position.asc()).all()
            peaks_count = len(peaks)
            peaks_history = [
                {
                    "id": p.id,
                    "video_position": p.video_position,
                    "watched_at": p.created_at.isoformat()
                }
                for p in peaks
            ]
        result["peaks_count"] = peaks_count
        result["peaks_history"] = peaks_history
        
        ext_ids = {
            "tmdb": tmdb_id
        }
        imdb_id = tmdb_data.get("imdb_id") or (match.imdb_id if match else None)
        if imdb_id:
            ext_ids["imdb"] = imdb_id

        from app.domains.library.services.detail.external_links import generate_external_links
        result["external_links"] = generate_external_links(ext_ids, "movie")
        return MovieDetailResponse(**result)
