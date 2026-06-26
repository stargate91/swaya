import logging
from typing import Any
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider
from app.domains.users.models import UserOverride
from app.application.library.schemas import MovieDetailResponse
from app.domains.library.services.detail.formatters.base import MovieDetailFormatter

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
            except:
                pass
                
        cast = []
        for perf in movie_data.get("performers") or []:
            gender_str = str(perf.get("gender") or "").upper()
            mapped_gender = 0
            if "FEMALE" in gender_str:
                mapped_gender = 1
            elif "MALE" in gender_str:
                mapped_gender = 2
                
            cast.append({
                "id": perf.get("id"),
                "name": perf.get("name"),
                "character": None,
                "job": "Actor",
                "profile_path": perf.get("image"),
                "popularity": perf.get("rating_porndb") or 0.0,
                "gender": mapped_gender
            })
            
        poster_url = movie_data.get("poster")
        backdrop_url = None
                
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
            "runtime": None,
            "rating_tmdb": 0.0,
            "rating_porndb": movie_data.get("rating"),
            "rating_imdb": None,
            "rating_rotten": None,
            "rating_meta": None,
            "vote_count_tmdb": 0,
            "budget": None,
            "revenue": None,
            "companies": [],
            "networks": [],
            "poster_path": poster_url,
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
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "custom_tags": [t.name for t in override.tags] if (override and override.tags) else [],
            "suggested_tags": [t.get("name") for t in movie_data.get("tags") or [] if t.get("name")] if movie_data.get("tags") else [],
            "tags": [],
            "is_tracked": override.is_tracked if override else False,
            "watch_count": override.watch_count if override else 0,
            "is_watched": override.is_watched if override else False,
            "resume_position": override.resume_position if override else 0,
            "last_watched_at": override.last_watched_at.isoformat() if (override and override.last_watched_at) else None,
            "playback_logs": [],
            "in_library": False,
        }
        return MovieDetailResponse(**result)
