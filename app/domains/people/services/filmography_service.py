import math
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.shared_kernel.enums import MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import MediaPersonLink
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.domains.media_assets.services.images import image_processing_service

logger = logging.getLogger(__name__)

class FilmographyService:
    def __init__(self, db: Session):
        self.db = db

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return image_processing_service.resolve_image_url(path, subfolder, size)


    def aggregate_credits(self, person_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        db = self.db
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        
        # Load credits linked to this person
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.MATCHED, ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        movies = []
        tv_map = {}
        scenes = []
        
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            credit_entry = {
                "id": item.id,
                "title": title,
                "type": match.media_type.value,
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops", size="original"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            }
            
            if match.media_type == MediaType.SCENE:
                scenes.append(credit_entry)
            elif match.media_type == MediaType.MOVIE:
                movies.append(credit_entry)
            elif match.media_type in (MediaType.TV, MediaType.EPISODE):
                sid = match.parent_id or match.id
                if sid not in tv_map:
                    tv_map[sid] = credit_entry
        
        return movies, list(tv_map.values()), scenes

    def get_combined_filmography(
        self,
        person_id: int,
        tmdb_id: Optional[str],
        ui_lang: str,
        tmdb_client: Any,
        is_adult: bool,
        known_for_department: Optional[str],
        person_name: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        # Get local library credits
        local_movies, local_tv, local_scenes = self.aggregate_credits(person_id)

        if not tmdb_id:
            local_movies.sort(key=lambda x: x.get("year") or 0, reverse=True)
            local_tv.sort(key=lambda x: x.get("year") or 0, reverse=True)
            local_scenes.sort(key=lambda x: x.get("year") or 0, reverse=True)
            from app.domains.people.helpers import select_known_for
            known_for = select_known_for(
                local_movies + local_tv,
                known_for_department,
                limit=4,
                adult_only=is_adult,
                person_name=person_name
            )
            return local_movies, local_tv, local_scenes, known_for

        try:
            tmdb_data = tmdb_client.get_person_details(int(tmdb_id), language=ui_lang)
        except Exception as e:
            logger.error(f"Failed to fetch TMDB credits for person {person_id}: {e}")
            tmdb_data = {}

        credits_data = tmdb_data.get("combined_credits", {})
        cast_list = credits_data.get("cast", []) or []
        crew_list = credits_data.get("crew", []) or []

        # Map local items for fast lookup by tmdb ID
        local_movies_map = {m["tmdb_id"]: m for m in local_movies if m.get("tmdb_id")}
        local_tv_map = {t["tmdb_id"]: t for t in local_tv if t.get("tmdb_id")}

        combined_credits = {}
        lead_cast_order_threshold = 3

        for credit in cast_list + crew_list:
            cid = credit.get("id")
            media_type = credit.get("media_type")
            if not cid or media_type not in {"movie", "tv"}:
                continue

            key = (cid, media_type)
            
            if "character" in credit and credit["character"]:
                role = f"as {credit['character']}"
            elif "job" in credit and credit["job"]:
                role = credit["job"]
            else:
                role = "Actor" if media_type == "movie" else "Cast"

            is_lead = (
                media_type in ("movie", "tv")
                and bool(credit.get("character"))
                and isinstance(credit.get("order"), int)
                and credit["order"] <= lead_cast_order_threshold
            )

            if key not in combined_credits:
                date_str = credit.get("release_date") if media_type == "movie" else credit.get("first_air_date")
                year = None
                if date_str:
                    try:
                        year = int(str(date_str).split("-")[0])
                    except Exception:
                        pass

                title = credit.get("title") if media_type == "movie" else credit.get("name")
                in_library = False
                library_item_id = None

                if media_type == "movie" and cid in local_movies_map:
                    in_library = True
                    library_item_id = local_movies_map[cid]["id"]
                elif media_type == "tv" and cid in local_tv_map:
                    in_library = True
                    library_item_id = local_tv_map[cid]["id"]

                combined_credits[key] = {
                    "id": library_item_id or cid,
                    "tmdb_id": cid,
                    "title": title or "Unknown",
                    "type": "movie" if media_type == "movie" else "tv",
                    "media_type": media_type,
                    "year": year,
                    "poster_path": self._resolve_img(credit.get("poster_path"), "posters"),
                    "backdrop_path": credit.get("backdrop_path"),  # Keep raw relative path for resolve_person_known_for_backdrop
                    "rating": credit.get("vote_average") or 0.0,
                    "rating_tmdb": credit.get("vote_average") or 0.0,
                    "vote_count": credit.get("vote_count") or 0,
                    "popularity": credit.get("popularity") or 0.0,
                    "genre_ids": credit.get("genre_ids") or [],
                    "roles": [role],
                    "is_lead": is_lead,
                    "order": credit.get("order") if isinstance(credit.get("order"), int) else None,
                    "character": credit.get("character"),
                    "in_library": in_library,
                }
            else:
                if role and role not in combined_credits[key]["roles"]:
                    combined_credits[key]["roles"].append(role)
                if is_lead:
                    combined_credits[key]["is_lead"] = True

        parsed_movies = []
        parsed_tv = []
        ordered_credits = []

        for credit in combined_credits.values():
            serialized_credit = {
                **credit,
                "job": ", ".join(credit["roles"]),
            }
            del serialized_credit["roles"]
            # Resolve the backdrop_path for the returned credits payload
            serialized_credit["backdrop_path"] = self._resolve_img(serialized_credit["backdrop_path"], "backdrops", size="original")
            ordered_credits.append(serialized_credit)
            if serialized_credit["media_type"] == "movie":
                parsed_movies.append(serialized_credit)
            else:
                parsed_tv.append(serialized_credit)

        # Merge back local items not in TMDB credits
        matched_local_movie_ids = {c["tmdb_id"] for c in parsed_movies if c.get("tmdb_id")}
        for m in local_movies:
            if m.get("tmdb_id") and m["tmdb_id"] not in matched_local_movie_ids:
                parsed_movies.append(m)
                ordered_credits.append(m)

        matched_local_tv_ids = {c["tmdb_id"] for c in parsed_tv if c.get("tmdb_id")}
        for t in local_tv:
            if t.get("tmdb_id") and t["tmdb_id"] not in matched_local_tv_ids:
                parsed_tv.append(t)
                ordered_credits.append(t)

        from app.domains.people.helpers import select_known_for
        known_for = select_known_for(
            ordered_credits,
            known_for_department,
            limit=8,
            adult_only=is_adult,
            person_name=person_name
        )

        def prioritize_person_credits(items: List[dict], known_for_items: List[dict]) -> List[dict]:
            if not items:
                return []
            
            known_for_keys = {}
            for index, entry in enumerate(known_for_items or []):
                tid = entry.get("tmdb_id")
                mtype = entry.get("media_type") or entry.get("type")
                if tid:
                    known_for_keys[(tid, mtype)] = index

            prioritized = []
            for entry in items:
                tid = entry.get("tmdb_id")
                mtype = entry.get("media_type") or entry.get("type")
                rank = known_for_keys.get((tid, mtype))
                is_known = rank is not None
                prioritized.append({
                    **entry,
                    "is_known_for": is_known,
                    "known_for_rank": rank if is_known else 10**9
                })

            prioritized.sort(
                key=lambda entry: (
                    0 if entry.get("is_known_for") else 1,
                    entry.get("known_for_rank", 10**9),
                    0 if entry.get("in_library") else 1,
                    -(int(entry.get("year") or 0))
                )
            )
            return prioritized

        parsed_movies = prioritize_person_credits(parsed_movies, known_for)
        parsed_tv = prioritize_person_credits(parsed_tv, known_for)
        local_scenes.sort(key=lambda x: x.get("year") or 0, reverse=True)

        return parsed_movies, parsed_tv, local_scenes, known_for

    def get_person_movies(self, person_id: int, page: int = 1, page_size: int = 12, source: Optional[str] = None):
        db = self.db
        # Load movie credits
        query = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type == MediaType.MOVIE,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.MATCHED, ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        )
        if source:
            try:
                from app.shared_kernel.enums import Provider
                provider_enum = Provider(source.lower())
                query = query.filter(MetadataMatch.provider == provider_enum)
            except ValueError:
                pass
        links = query.all()
        
        movies = []
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            movies.append({
                "id": item.id,
                "title": title,
                "type": "movie",
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops", size="original"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            })
            
        total_items = len(movies)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = movies[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }

    def get_person_tv(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        # Load tv credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE]),
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.MATCHED, ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        tv_map = {}
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            sid = match.parent_id or match.id
            if sid not in tv_map:
                tv_map[sid] = {
                    "id": item.id,
                    "title": title,
                    "type": "tv",
                    "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                    "year": match.release_date.year if match.release_date else None,
                    "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                    "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops", size="original"),
                    "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                    "rating_porndb": match.rating_porndb,
                    "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                    "character": link.character_name,
                    "in_library": True,
                }
                
        tv_list = list(tv_map.values())
        total_items = len(tv_list)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = tv_list[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }

    def get_person_scenes(self, person_id: int, page: int = 1, page_size: int = 12, source: Optional[str] = None):
        db = self.db
        # Load scene credits
        query = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type == MediaType.SCENE,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.MATCHED, ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        )
        if source:
            try:
                from app.shared_kernel.enums import Provider
                provider_enum = Provider(source.lower())
                query = query.filter(MetadataMatch.provider == provider_enum)
            except ValueError:
                pass
        links = query.all()
        
        scenes = []
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            scenes.append({
                "id": item.id,
                "title": title,
                "type": "scene",
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops", size="original"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            })
            
        total_items = len(scenes)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = scenes[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }


