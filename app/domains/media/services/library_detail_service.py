import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from fastapi.responses import JSONResponse

from app.core.enums import Provider, MediaType, ItemStatus, RoleType
from app.domains.media.models.filesystem import MediaItem, ExtraFile
from app.domains.media.models.metadata import MetadataMatch, MetadataLocalization, MediaCollection, MediaCollectionLocalization
from app.domains.people.models import Person, PersonLocalization, MediaPersonLink
from app.domains.users.models import UserOverride, Tag
from app.domains.shared.ports.scrapers import ScraperGatewayPort
from app.core.images import ImageProcessingService
from app.core.language import LanguageService

from app.core.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class LibraryDetailService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        self.db = db
        self.scrapers = scrapers
        self.img_service = ImageProcessingService()
        self.tmdb_scraper = scrapers.tmdb(db)

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        if not path:
            return None
        return self.img_service.resolve_image_url(path, subfolder, size)

    def get_library_item_detail(self, item_id: str, full_people: bool = False):
        db = self.db
        
        # 1. Virtual StashDB / FansDB Scene Detail
        if isinstance(item_id, str) and item_id.startswith("stash_"):
            scene_uuid = item_id.split("_")[1]
            stash_scraper = self.scrapers.adult(Provider.STASHDB, db)
            scene_data = stash_scraper.fetch_scene(scene_uuid)
            if not scene_data:
                fans_scraper = self.scrapers.adult(Provider.FANSDB, db)
                scene_data = fans_scraper.fetch_scene(scene_uuid)
            
            if not scene_data:
                return JSONResponse(status_code=404, content={"error": "Scene not found on StashDB/FansDB"})
            
            title = scene_data.get("title") or "Unknown Scene"
            images = scene_data.get("images") or []
            poster_url = images[0].get("url") if images else None
            
            date_str = scene_data.get("date")
            year = None
            if date_str:
                try:
                    year = int(date_str.split("-")[0])
                except:
                    pass
            
            duration_sec = scene_data.get("duration")
            duration_str = None
            if duration_sec:
                try:
                    duration_min = int(float(duration_sec) / 60)
                    if duration_min > 0:
                        duration_str = f"{duration_min} min"
                except:
                    pass
            
            studio_data = scene_data.get("studio") or {}
            studio_name = studio_data.get("name")
            studio_images = studio_data.get("images") or []
            studio_logo = studio_images[0].get("url") if studio_images else None
            
            parent_data = studio_data.get("parent") or {}
            parent_name = parent_data.get("name")
            parent_images = parent_data.get("images") or []
            parent_logo = parent_images[0].get("url") if parent_images else None
            
            cast = []
            for p_entry in scene_data.get("performers") or []:
                perf = p_entry.get("performer") or {}
                p_images = perf.get("images") or []
                p_img = p_images[0].get("url") if p_images else None
                gender_str = str(perf.get("gender") or "").upper()
                mapped_gender = 0
                if "FEMALE" in gender_str:
                    mapped_gender = 1
                elif "MALE" in gender_str:
                    mapped_gender = 2
                elif gender_str:
                    mapped_gender = 3
                
                cast.append({
                    "id": perf.get("id"),
                    "name": perf.get("name"),
                    "character": None,
                    "job": "Actor",
                    "profile_path": p_img,
                    "popularity": perf.get("rating_porndb") or 0,
                    "rating_porndb": perf.get("rating_porndb"),
                    "scene_count": perf.get("scene_count"),
                    "gender": mapped_gender
                })
            
            # Look up local overrides if any exist
            override = db.query(UserOverride).filter(
                UserOverride.user_id == 1,
                UserOverride.custom_title == title
            ).first() # Fallback approximation
            
            result = {
                "id": f"stash_{scene_uuid}",
                "title": title,
                "logo_path": self._resolve_img(studio_logo or parent_logo, "logos"),
                "original_logo_path": studio_logo or parent_logo,
                "original_backdrop_path": poster_url,
                "original_title": None,
                "tagline": None,
                "overview": scene_data.get("details"),
                "genres": [],
                "year": year,
                "release_date": date_str,
                "runtime": duration_sec,
                "formatted_duration": duration_str,
                "rating_tmdb": 0.0,
                "vote_count_tmdb": 0,
                "companies": [{"name": studio_name, "logo_path": self._resolve_img(studio_logo, "logos")}] if studio_name else [],
                "networks": [{"name": parent_name, "logo_path": self._resolve_img(parent_logo, "logos")}] if parent_name else [],
                "poster_path": poster_url,
                "backdrop_path": None,
                "original_language": None,
                "type": "scene",
                "cast": cast,
                "cast_total": len(cast),
                "people_complete": True,
                "directors": [],
                "writers": [],
                "is_adult": True,
                "is_favorite": override.is_favorite if override else False,
                "user_rating": override.user_rating if override else None,
                "user_comment": override.user_comment if override else None,
                "external_ids": {
                    "stash_id": scene_uuid,
                },
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
            return JSONResponse(content=result)
        
        # 2. Virtual TMDB Movie Detail
        if isinstance(item_id, str) and item_id.startswith("tmdb_"):
            try:
                tmdb_id = int(item_id.split("_")[1])
            except (ValueError, IndexError):
                return JSONResponse(status_code=400, content={"error": "Invalid TMDB ID format"})
            
            # Fetch details via Scraper
            ui_lang = DEFAULT_FALLBACK_LANGUAGE # Default UI language
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
            
            # Local override check
            override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
                UserOverride.user_id == 1,
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
            return JSONResponse(content=result)
        
        # 3. Local MediaItem Detail
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
        
        # Load user override
        override = item.overrides
        if not override:
            # Fallback to query
            override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item.id).first()
            
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
        return JSONResponse(content=result)

    def get_library_tv_detail(self, tv_tmdb_id: str, seasons_limit: int = 5, initial_episodes_limit: int = 4):
        db = self.db
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        tmdb_data = self.tmdb_scraper.get_details(tv_tmdb_id_int, "tv", language=ui_lang)
        if not tmdb_data:
            return JSONResponse(status_code=404, content={"error": "TV Show not found on TMDB"})
        
        # Load local episodes to see what is in the library
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        local_episodes_map = {}
        for item in local_items:
            for match in item.matches:
                if match.season_number is not None and match.episode_number is not None:
                    # episode_number can be a list or single int
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            local_episodes_map[(match.season_number, num)] = item
                    else:
                        local_episodes_map[(match.season_number, int(ep_num))] = item
        
        seasons = []
        all_season_meta = sorted(tmdb_data.get("seasons", []), key=lambda x: x.get("season_number") or 0)
        
        for idx, season_meta in enumerate(all_season_meta[:seasons_limit]):
            season_number = season_meta.get("season_number")
            if season_number is None:
                continue
            
            # Fetch season details to get episodes list
            season_detail = self.tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
            all_episodes = season_detail.get("episodes", []) or []
            
            episodes = []
            for ep in all_episodes[:initial_episodes_limit]:
                ep_num = ep.get("episode_number")
                local_item = local_episodes_map.get((season_number, ep_num))
                
                # Check for watch states/overrides
                override = None
                if local_item:
                    override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == local_item.id).first()
                
                episodes.append({
                    "id": f"tmdb_{tv_tmdb_id_int}_{season_number}_{ep_num}",
                    "episode_number": ep_num,
                    "title": ep.get("name") or f"Episode {ep_num}",
                    "overview": ep.get("overview"),
                    "still_path": self._resolve_img(ep.get("still_path"), "stills"),
                    "runtime": ep.get("runtime"),
                    "rating_tmdb": ep.get("vote_average"),
                    "vote_count_tmdb": ep.get("vote_count"),
                    "air_date": ep.get("air_date"),
                    "path": local_item.current_path if local_item else None,
                    "filename": local_item.filename if local_item else None,
                    "watch_count": override.watch_count if override else 0,
                    "is_watched": override.is_watched if override else False,
                    "resume_position": override.resume_position if override else 0,
                    "in_library": local_item is not None,
                    "is_missing": local_item is None,
                })
            
            seasons.append({
                "season_number": season_number,
                "title": season_meta.get("name") or f"Season {season_number}",
                "overview": season_meta.get("overview"),
                "poster_path": self._resolve_img(season_meta.get("poster_path"), "posters"),
                "air_date": season_meta.get("air_date"),
                "episode_count": season_meta.get("episode_count") or len(all_episodes),
                "episodes_loaded_count": len(episodes),
                "episodes": episodes,
            })
            
        credits = tmdb_data.get("credits", {})
        cast = []
        directors = []
        writers = []
        
        for actor in credits.get("cast", [])[:15]:
            cast.append({
                "id": actor.get("id"),
                "name": actor.get("name"),
                "character": actor.get("character"),
                "profile_path": self._resolve_img(actor.get("profile_path"), "people"),
            })
            
        for crew in credits.get("crew", []):
            crew_member = {
                "id": crew.get("id"),
                "name": crew.get("name"),
                "job": crew.get("job"),
                "profile_path": self._resolve_img(crew.get("profile_path"), "people"),
            }
            if crew.get("job") == "Director":
                directors.append(crew_member)
            elif crew.get("job") in ("Writer", "Screenplay"):
                writers.append(crew_member)
        
        # Load user override
        override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
            UserOverride.user_id == 1,
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tv_tmdb_id_int)
        ).first()
        
        result = {
            "id": f"tmdb_{tv_tmdb_id_int}",
            "tv_tmdb_id": tv_tmdb_id_int,
            "imdb_id": tmdb_data.get("external_ids", {}).get("imdb_id"),
            "title": tmdb_data.get("name") or tmdb_data.get("original_name") or "Unknown TV Show",
            "logo_path": None,
            "backdrop_path": self._resolve_img(tmdb_data.get("backdrop_path"), "backdrops"),
            "poster_path": self._resolve_img(tmdb_data.get("poster_path"), "posters"),
            "year": int(tmdb_data.get("first_air_date", "").split("-")[0]) if tmdb_data.get("first_air_date") else None,
            "first_air_date": tmdb_data.get("first_air_date"),
            "last_air_date": tmdb_data.get("last_air_date"),
            "release_status": tmdb_data.get("status"),
            "number_of_seasons": tmdb_data.get("number_of_seasons") or len(seasons),
            "number_of_episodes": tmdb_data.get("number_of_episodes") or 0,
            "overview": tmdb_data.get("overview"),
            "rating_tmdb": tmdb_data.get("vote_average"),
            "genres": [g["name"] for g in tmdb_data.get("genres", [])] if tmdb_data.get("genres") else [],
            "type": "tv",
            "cast": cast,
            "directors": directors,
            "writers": writers,
            "seasons": seasons,
            "companies": [{"name": c.get("name"), "logo_path": self._resolve_img(c.get("logo_path"), "logos")} for c in tmdb_data.get("production_companies", [])] if tmdb_data.get("production_companies") else [],
            "networks": [{"name": n.get("name"), "logo_path": self._resolve_img(n.get("logo_path"), "logos")} for n in tmdb_data.get("networks", [])] if tmdb_data.get("networks") else [],
            "is_adult": tmdb_data.get("adult", False),
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "is_tracked": override.is_tracked if override else False,
            "in_library": len(local_items) > 0,
        }
        return JSONResponse(content=result)
 
    def get_library_tv_season_detail(self, tv_tmdb_id: str, season_number: int):
        db = self.db
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        season_detail = self.tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
        if not season_detail:
            return JSONResponse(status_code=404, content={"error": "Season not found"})
        
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.season_number == season_number,
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        local_episodes_map = {}
        for item in local_items:
            for match in item.matches:
                if match.episode_number is not None:
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            local_episodes_map[num] = item
                    else:
                        local_episodes_map[int(ep_num)] = item
        
        episodes = []
        all_episodes = season_detail.get("episodes", []) or []
        for ep in all_episodes:
            ep_num = ep.get("episode_number")
            local_item = local_episodes_map.get(ep_num)
            
            override = None
            if local_item:
                override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == local_item.id).first()
            
            episodes.append({
                "id": f"tmdb_{tv_tmdb_id_int}_{season_number}_{ep_num}",
                "episode_number": ep_num,
                "title": ep.get("name") or f"Episode {ep_num}",
                "overview": ep.get("overview"),
                "still_path": self._resolve_img(ep.get("still_path"), "stills"),
                "runtime": ep.get("runtime"),
                "rating_tmdb": ep.get("vote_average"),
                "vote_count_tmdb": ep.get("vote_count"),
                "air_date": ep.get("air_date"),
                "path": local_item.current_path if local_item else None,
                "filename": local_item.filename if local_item else None,
                "watch_count": override.watch_count if override else 0,
                "is_watched": override.is_watched if override else False,
                "resume_position": override.resume_position if override else 0,
                "in_library": local_item is not None,
                "is_missing": local_item is None,
            })
            
        result = {
            "season_number": season_number,
            "title": season_detail.get("name") or f"Season {season_number}",
            "overview": season_detail.get("overview"),
            "poster_path": self._resolve_img(season_detail.get("poster_path"), "posters"),
            "air_date": season_detail.get("air_date"),
            "episode_count": len(all_episodes),
            "episodes_loaded_count": len(episodes),
            "episodes": episodes,
        }
        return JSONResponse(content=result)

    def get_collection_detail(self, collection_tmdb_id: str, language: str | None = None):
        db = self.db
        try:
            collection_tmdb_id_int = int(collection_tmdb_id)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid collection TMDB ID"})
        
        ui_lang = language or DEFAULT_FALLBACK_LANGUAGE
        
        # Call TMDB API via Scraper
        tmdb_details = {}
        try:
            tmdb_details = self.tmdb_scraper._call_api(
                f"/collection/{collection_tmdb_id_int}",
                {"language": ui_lang}
            ) or {}
        except Exception:
            tmdb_details = {}
            
        # Get local items in this collection
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MediaItem.status.in_([ItemStatus.ORGANIZED, ItemStatus.RENAMED]),
            MediaItem.item_type == MediaType.MOVIE,
            MetadataMatch.collection_id != None,
            MetadataMatch.is_active == True,
        ).all()
        
        # Filter items belonging to the collection
        collection_items = []
        for item in local_items:
            for match in item.matches:
                if match.collection and match.collection.external_id == str(collection_tmdb_id_int):
                    collection_items.append(item)
                    break
        
        owned_tmdb_ids = set()
        movies = []
        
        for item in collection_items:
            active_match = next((m for m in item.matches if m.is_active), None)
            if not active_match:
                continue
            owned_tmdb_ids.add(active_match.tmdb_id)
            loc = LanguageService.get_best_localization(active_match.localizations, ui_lang)
            
            movies.append({
                "id": item.id,
                "tmdb_id": active_match.tmdb_id,
                "library_item_id": item.id,
                "title": loc.title if loc else item.filename,
                "year": active_match.release_date.year if active_match.release_date else None,
                "poster_path": self._resolve_img(loc.poster_path if loc else None, "posters"),
                "backdrop_path": self._resolve_img(active_match.backdrop_path, "backdrops"),
                "rating": active_match.rating_porndb or active_match.rating_tmdb or 0.0,
                "rating_porndb": active_match.rating_porndb,
                "type": item.item_type.value,
                "path": item.current_path,
                "in_library": True,
            })
            
        # Append virtual parts not owned
        for part in tmdb_details.get("parts", []) or []:
            part_tmdb_id = part.get("id")
            if not part_tmdb_id or part_tmdb_id in owned_tmdb_ids:
                continue
            
            release_date = part.get("release_date")
            year = None
            if release_date:
                try:
                    year = int(release_date.split("-")[0])
                except:
                    pass
            
            movies.append({
                "id": part_tmdb_id,
                "tmdb_id": part_tmdb_id,
                "library_item_id": None,
                "title": part.get("title") or part.get("original_title") or f"Movie {part_tmdb_id}",
                "year": year,
                "poster_path": self._resolve_img(part.get("poster_path"), "posters"),
                "backdrop_path": self._resolve_img(part.get("backdrop_path"), "backdrops"),
                "rating": part.get("vote_average") or 0.0,
                "type": "movie",
                "path": None,
                "in_library": False,
            })
            
        movies.sort(key=lambda x: (0 if x["in_library"] else 1, -(x["year"] or 0), x["title"]))
        
        result = {
            "tmdb_id": collection_tmdb_id_int,
            "title": tmdb_details.get("name") or f"Collection {collection_tmdb_id_int}",
            "overview": tmdb_details.get("overview"),
            "poster_path": self._resolve_img(tmdb_details.get("poster_path"), "posters"),
            "backdrop_path": self._resolve_img(tmdb_details.get("backdrop_path"), "backdrops"),
            "owned_count": len(owned_tmdb_ids),
            "total_count": len(movies),
            "movies": movies,
        }
        return JSONResponse(content=result)
