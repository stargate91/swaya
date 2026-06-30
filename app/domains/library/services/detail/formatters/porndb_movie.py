import logging
from typing import Any
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType
from app.domains.users.models import UserOverride
from app.application.library.schemas import MovieDetailResponse
from app.domains.library.services.detail.formatters.base import MovieDetailFormatter
from app.domains.metadata.models import MetadataMatch

from app.domains.people.models import Person, ExternalSourceLink

logger = logging.getLogger(__name__)

class PornDbMovieFormatter(MovieDetailFormatter):
    def format(self, item_id: Any, db: Any, scrapers: Any, current_uid: Any) -> Any:
        try:
            porndb_id = item_id.split("_")[1]
        except IndexError:
            return JSONResponse(status_code=400, content={"error": "Invalid PornDB ID format"})
            
        porndb_scraper = scrapers.adult(Provider.PORNDB, db)
        movie_data = porndb_scraper.fetch_movie(porndb_id)
        if not movie_data:
            return JSONResponse(status_code=404, content={"error": "Movie not found on PornDB"})
            
        override = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            UserOverride.custom_title == (movie_data.get("title") or "Unknown Movie")
        ).first()
            
        date_str = movie_data.get("date")
        year = None
        if date_str:
            try:
                year = int(date_str.split("-")[0])
            except Exception as e:
                logger.debug(f"Swallowed exception in domains/library/services/detail/formatters/porndb_movie.py:37: {e}", exc_info=True)
                
        cast = []
        for perf in movie_data.get("performers") or []:
            p_info = perf.get("parent") or perf.get("performer") or perf
            perf_name = p_info.get("name")
            if not perf_name:
                continue
            gender_str = str(p_info.get("gender") or p_info.get("extras", {}).get("gender") or p_info.get("extra", {}).get("gender") or "").upper()
            mapped_gender = 0
            if "FEMALE" in gender_str:
                mapped_gender = 1
            elif "MALE" in gender_str:
                mapped_gender = 2
                
            # Check if person exists in DB
            person_db = None
            p_ext_id = p_info.get("id")
            if p_ext_id:
                link = db.query(ExternalSourceLink).filter(
                    ExternalSourceLink.provider == Provider.PORNDB,
                    ExternalSourceLink.external_id == str(p_ext_id)
                ).first()
                if link:
                    person_db = link.person

            if not person_db:
                person_db = db.query(Person).filter(Person.name == perf_name).first()

            if person_db:
                p_id = f"local:{person_db.id}"
                # Check for UserOverride custom profile image
                override_obj = db.query(UserOverride).filter(
                    UserOverride.user_id == current_uid,
                    UserOverride.person_id == person_db.id
                ).first()
                custom_img = override_obj.custom_poster if override_obj else None
                resolved_img = self._resolve_img(custom_img or person_db.local_profile_path or person_db.profile_path, "people")
            else:
                p_id = f"porndb:{p_info.get('id')}"
                resolved_img = p_info.get("image")
                
            cast.append({
                "id": p_id,
                "name": perf_name,
                "character": None,
                "job": "Actor",
                "profile_path": resolved_img,
                "popularity": p_info.get("rating_porndb") or 0.0,
                "gender": mapped_gender
            })
            
        poster_url = movie_data.get("poster")
        backdrop_url = None

        match = db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.PORNDB,
            MetadataMatch.external_id == str(porndb_id),
            MetadataMatch.media_type == MediaType.MOVIE
        ).first()

        if match:
            db_updated = False
            if not match.backdrop_path and backdrop_url:
                match.backdrop_path = backdrop_url
                db_updated = True
            if not match.release_date and date_str:
                from datetime import datetime
                try:
                    match.release_date = datetime.strptime(date_str, "%Y-%m-%d")
                    db_updated = True
                except Exception as e:
                    logger.debug(f"Swallowed exception in domains/library/services/detail/formatters/porndb_movie.py:91: {e}", exc_info=True)
            if movie_data.get("rating") is not None and float(movie_data.get("rating")) > 0:
                try:
                    match.rating_porndb = float(movie_data.get("rating"))
                    db_updated = True
                except Exception as e:
                    logger.debug(f"Swallowed exception in domains/library/services/detail/formatters/porndb_movie.py:97: {e}", exc_info=True)
            
            loc_db = next((l for l in match.localizations if l.locale == "en"), None)
            if not loc_db:
                from app.domains.metadata.models import MetadataLocalization
                loc_db = MetadataLocalization(
                    match_id=match.id,
                    locale="en",
                    title=movie_data.get("title") or "Unknown Movie",
                    overview=movie_data.get("description"),
                    poster_path=poster_url
                )
                db.add(loc_db)
                db_updated = True
            else:
                if not loc_db.title and movie_data.get("title"):
                    loc_db.title = movie_data.get("title")
                    db_updated = True
                if not loc_db.overview and movie_data.get("description"):
                    loc_db.overview = movie_data.get("description")
                    db_updated = True
                if not loc_db.poster_path and poster_url:
                    loc_db.poster_path = poster_url
                    db_updated = True
            
            if db_updated:
                db.commit()

        metadata_override = None
        if match:
            metadata_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.metadata_match_id == match.id
            ).first()

        physical_override = None
        if match and match.media_item_id:
            physical_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.media_item_id == match.media_item_id
            ).first()

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

        # Use metadata_override if available, else fallback to override
        effective_override = metadata_override if metadata_override else override

        companies = []
        site = movie_data.get("site")
        if site and site.get("name"):
            companies.append({
                "name": site.get("name"),
                "logo_path": self._resolve_img(site.get("logo") or site.get("image") or site.get("poster"), "logos")
            })

            parent_site = site.get("parent") or site.get("network")
            if isinstance(parent_site, dict) and parent_site.get("name"):
                companies.append({
                    "name": parent_site.get("name"),
                    "logo_path": self._resolve_img(parent_site.get("logo") or parent_site.get("image") or parent_site.get("poster"), "logos")
                })

        networks = []

        duration_val = None
        duration_raw = movie_data.get("duration")
        if duration_raw:
            if isinstance(duration_raw, (int, float)):
                duration_val = int(duration_raw)
            elif isinstance(duration_raw, str):
                val = duration_raw.strip()
                if val.isdigit():
                    duration_val = int(val)
                else:
                    parts = val.split(":")
                    try:
                        if len(parts) == 2:
                            duration_val = int(parts[0]) * 60 + int(parts[1])
                        elif len(parts) == 3:
                            duration_val = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    except ValueError as e:
                        logger.debug(f"Swallowed exception in domains/library/services/detail/formatters/porndb_movie.py:217: {e}", exc_info=True)

        result = {
            "id": f"porndb_{porndb_id}",
            "title": movie_data.get("title") or "Unknown Movie",
            "keywords": [],
            "trailer_key": movie_data.get("trailer"),
            "logo_path": None,
            "original_title": movie_data.get("title"),
            "tagline": None,
            "overview": movie_data.get("description"),
            "genres": [],
            "year": year,
            "release_date": date_str,
            "runtime": (duration_val // 60) if duration_val else None,
            "rating_tmdb": None,
            "rating_porndb": movie_data.get("rating"),
            "rating_imdb": None,
            "rating_rotten": None,
            "rating_meta": None,
            "vote_count_tmdb": None,
            "budget": None,
            "revenue": None,
            "companies": companies,
            "networks": networks,
            "poster_path": self._resolve_img(effective_override.custom_poster if (effective_override and effective_override.custom_poster) else poster_url, "posters"),
            "backdrop_path": backdrop_url,
            "original_language": "en",
            "type": "movie",
            "tmdb_id": 0,
            "collection_data": None,
            "cast": cast,
            "cast_total": len(cast),
            "people_complete": True,
            "directors": [],
            "writers": [],
            "is_adult": True,
            "is_favorite": effective_override.is_favorite if effective_override else False,
            "user_rating": effective_override.user_rating if effective_override else None,
            "user_comment": effective_override.user_comment if effective_override else None,
            "custom_tags": [t.name for t in effective_override.tags if t.is_adult == True] if (effective_override and effective_override.tags) else [],
            "suggested_tags": [t.get("name") for t in movie_data.get("tags") or [] if t.get("name")] if movie_data.get("tags") else [],
            "tags": [],
            "is_tracked": effective_override.is_tracked if effective_override else False,
            "watch_count": watch_count,
            "is_watched": is_watched,
            "resume_position": resume_position,
            "last_watched_at": last_watched_at_dt.isoformat() if last_watched_at_dt else None,
            "playback_logs": playback_logs,
            "in_library": match is not None and match.media_item_id is not None,
            "library_item_id": match.media_item_id if (match and match.media_item_id) else None,
        }
        ext_ids = {
            "porndb_id": porndb_id,
            "source": "porndb"
        }
        from app.domains.library.services.detail.external_links import generate_external_links
        result["external_links"] = generate_external_links(ext_ids, "movie")
        return MovieDetailResponse(**result)
