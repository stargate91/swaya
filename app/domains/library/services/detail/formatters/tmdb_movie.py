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
        cast = []
        directors = []
        writers = []
        
        for actor in credits.get("cast", [])[:15]:
            cast.append({
                "id": actor.get("id"),
                "name": actor.get("name"),
                "character": actor.get("character"),
                "job": "Actor",
                "profile_path": self._resolve_img(actor.get("profile_path"), "people"),
                "popularity": actor.get("popularity", 0),
                "gender": actor.get("gender")
            })
        
        for crew in credits.get("crew", []):
            crew_member = {
                "id": crew.get("id"),
                "name": crew.get("name"),
                "job": crew.get("job"),
                "profile_path": self._resolve_img(crew.get("profile_path"), "people"),
                "popularity": crew.get("popularity", 0),
                "gender": crew.get("gender")
            }
            if crew.get("job") == "Director":
                directors.append(crew_member)
            elif crew.get("job") in ("Writer", "Screenplay"):
                writers.append(crew_member)
        
        release_date = tmdb_data.get("release_date")
        year = None
        if release_date:
            try:
                year = int(release_date.split("-")[0])
            except:
                pass
        
        override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
            UserOverride.user_id == current_uid,
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tmdb_id),
            MetadataMatch.media_type == MediaType.MOVIE
        ).first()
        
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
        
        match = db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tmdb_id),
            MetadataMatch.media_type == MediaType.MOVIE
        ).first()

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
            "is_adult": tmdb_data.get("adult", False),
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "custom_tags": [t.name for t in override.tags] if (override and override.tags) else [],
            "suggested_tags": [k["name"] for k in tmdb_data.get("keywords", {}).get("keywords", [])] if tmdb_data.get("keywords") else [],
            "tags": [],
            "is_tracked": override.is_tracked if override else False,
            "watch_count": override.watch_count if override else 0,
            "is_watched": override.is_watched if override else False,
            "resume_position": override.resume_position if override else 0,
            "last_watched_at": override.last_watched_at.isoformat() if override and override.last_watched_at else None,
            "playback_logs": [],
            "in_library": False,
        }
        return MovieDetailResponse(**result)
