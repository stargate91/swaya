import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import Person, MediaPersonLink
from app.domains.users.models import UserOverride
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.library.services.detail._detail_formatter import DetailFormatter

logger = logging.getLogger(__name__)

class MovieDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers
        self.tmdb_scraper = scrapers.tmdb(db)

    def get_library_item_detail(self, item_id: str, full_people: bool = False) -> MovieDetailResponse:
        from app.domains.library.schemas import MovieDetailResponse
        db = self.db
        
        # Tracked / External TMDB Movie Detail
        if isinstance(item_id, str) and item_id.startswith("tmdb_"):
            try:
                tmdb_id = int(item_id.split("_")[1])
            except (ValueError, IndexError):
                return JSONResponse(status_code=400, content={"error": "Invalid TMDB ID format"})
            
            ui_lang = DEFAULT_FALLBACK_LANGUAGE
            tmdb_data = self.tmdb_scraper.get_details(tmdb_id, "movie", language=ui_lang)
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
            
            from app.shared_kernel.user_context import get_current_user_id
            current_uid = get_current_user_id()
            override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
                UserOverride.user_id == current_uid,
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.external_id == str(tmdb_id)
            ).first()
            
            result = {
                "id": f"tmdb_{tmdb_id}",
                "title": tmdb_data.get("title") or tmdb_data.get("original_title") or "Unknown",
                "logo_path": None,
                "original_title": tmdb_data.get("original_title"),
                "tagline": tmdb_data.get("tagline"),
                "overview": tmdb_data.get("overview"),
                "genres": [g["name"] for g in tmdb_data.get("genres", [])] if tmdb_data.get("genres") else [],
                "year": year,
                "release_date": release_date,
                "runtime": tmdb_data.get("runtime"),
                "rating_tmdb": tmdb_data.get("vote_average"),
                "vote_count_tmdb": tmdb_data.get("vote_count"),
                "companies": [{"name": c.get("name"), "logo_path": self._resolve_img(c.get("logo_path"), "logos")} for c in tmdb_data.get("production_companies", [])] if tmdb_data.get("production_companies") else [],
                "networks": [],
                "poster_path": self._resolve_img(tmdb_data.get("poster_path"), "posters"),
                "backdrop_path": self._resolve_img(tmdb_data.get("backdrop_path"), "backdrops"),
                "original_language": tmdb_data.get("original_language"),
                "type": "movie",
                "tmdb_id": tmdb_id,
                "cast": cast,
                "cast_total": len(credits.get("cast", [])),
                "people_complete": True,
                "directors": directors,
                "writers": writers,
                "is_adult": tmdb_data.get("adult", False),
                "is_favorite": override.is_favorite if override else False,
                "user_rating": override.user_rating if override else None,
                "user_comment": override.user_comment if override else None,
                "custom_tags": [],
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
        
        # Local MediaItem Detail
        try:
            item_id_int = int(item_id)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid item ID"})
        
        item = db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.matches).joinedload(MetadataMatch.people).joinedload(MediaPersonLink.person).joinedload(Person.localizations),
            joinedload(MediaItem.matches).joinedload(MetadataMatch.studios),
            joinedload(MediaItem.extras),
            joinedload(MediaItem.playback_logs),
            joinedload(MediaItem.overrides),
        ).filter(MediaItem.id == item_id_int).first()
        
        if not item:
            return JSONResponse(status_code=404, content={"error": "Item not found"})
        
        active_match = next((m for m in item.matches if m.media_item_id == item.id), None)
        if not active_match and item.matches:
            active_match = item.matches[0]
            
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        loc = LanguageService.get_best_localization(active_match.localizations, ui_lang) if active_match else None
        
        cast = []
        directors = []
        writers = []
        
        if active_match:
            for link in sorted(active_match.people, key=lambda x: x.order):
                person = link.person
                person_data = {
                    "id": person.id,
                    "name": person.name,
                    "character": link.character_name,
                    "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                    "profile_path": self._resolve_img(person.profile_path, "people"),
                    "popularity": (
                        person.rating_porndb
                        if person.is_adult and person.rating_porndb is not None
                        else person.popularity or 0
                    ),
                    "scene_count": person.scene_count,
                    "rating_porndb": person.rating_porndb,
                    "gender": person.gender
                }
                if person_data["job"] == "Director":
                    directors.append(person_data)
                elif person_data["job"] == "Writer":
                    writers.append(person_data)
                elif person_data["job"] == "Actor":
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
        
        override = item.overrides
        if not override:
            override = db.query(UserOverride).filter(UserOverride.user_id == current_uid, UserOverride.media_item_id == item.id).first()
            
        title = (override.custom_title if (override and override.custom_title) else None) or (loc.title if loc else item.filename)
        overview = (override.custom_overview if (override and override.custom_overview) else None) or (loc.overview if loc else None)
        
        result = {
            "id": item.id,
            "title": title,
            "logo_path": self._resolve_img(loc.logo_path if loc else None, "logos"),
            "original_title": active_match.original_title if active_match else None,
            "tagline": loc.tagline if loc else None,
            "overview": overview,
            "genres": loc.genres if loc else [],
            "year": active_match.release_date.year if (active_match and active_match.release_date) else None,
            "release_date": active_match.release_date.isoformat() if (active_match and active_match.release_date) else None,
            "runtime": active_match.runtime if active_match else None,
            "rating_tmdb": active_match.rating_tmdb if active_match else 0.0,
            "rating_porndb": active_match.rating_porndb if active_match else None,
            "vote_count_tmdb": active_match.vote_count_tmdb if active_match else 0,
            "companies": [{"name": s.name, "logo_path": self._resolve_img(s.logo_path, "logos")} for s in active_match.studios] if active_match else [],
            "networks": [],
            "poster_path": self._resolve_img(loc.poster_path if loc else None, "posters"),
            "backdrop_path": self._resolve_img(active_match.backdrop_path if active_match else None, "backdrops"),
            "original_language": loc.original_language if loc else DEFAULT_FALLBACK_LANGUAGE,
            "type": active_match.media_type.value if active_match else "movie",
            "cast": cast,
            "cast_total": len(cast),
            "people_complete": True,
            "directors": directors,
            "writers": writers,
            "is_adult": active_match.is_adult if active_match else False,
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "technical": technical,
            "in_library": True,
            "path": item.current_path,
            "filename": item.filename,
            "watch_count": override.watch_count if override else 0,
            "is_watched": override.is_watched if override else False,
            "resume_position": override.resume_position if override else 0,
            "last_watched_at": override.last_watched_at.isoformat() if override and override.last_watched_at else None,
        }
        return MovieDetailResponse(**result)
