import logging
import math
from typing import Optional, List, Dict, Any
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType, ItemStatus, RoleType
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.people.models import Person, PersonLocalization, MediaPersonLink, ExternalSourceLink
from app.domains.settings.models import UserSetting
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.domains.media_assets.services.images import ImageProcessingService
from app.shared_kernel.language import LanguageService

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class PeopleDetailService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        self.db = db
        self.img_service = ImageProcessingService()
        self.tmdb = scrapers.tmdb(db)

    def _resolve_img(self, path: Optional[str], subfolder: str) -> Optional[str]:
        if not path:
            return None
        return self.img_service.resolve_image_url(path, subfolder)

    def get_people(
        self,
        search: str = None,
        role: str = None,
        sort_by: str = "library_count",
        include_inactive: bool = False,
        adult_only: bool = False,
        gender: str = "all",
        offset: int = 0,
        limit: int = 20,
    ):
        db = self.db
        
        # Determine target match IDs linked to library items
        matched_match_ids = [
            m.id for m in db.query(MetadataMatch).join(MediaItem).filter(
                MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
            ).filter(MetadataMatch.is_active == True).all()
        ]
        
        join_cond = (MediaPersonLink.person_id == Person.id)
        if matched_match_ids:
            join_cond = join_cond & (MediaPersonLink.match_id.in_(matched_match_ids))
        else:
            join_cond = join_cond & (False)

        library_key = case(
            (
                MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE, MediaType.SEASON]),
                -func.coalesce(MetadataMatch.parent_id, MetadataMatch.id)
            ),
            else_=func.coalesce(MetadataMatch.id)
        )

        query = db.query(
            Person,
            func.count(func.distinct(library_key)).label("library_count"),
            func.max(
                case(
                    (MetadataMatch.is_adult == True, 1),
                    else_=0
                )
            ).label("linked_adult_flag")
        ).select_from(Person).outerjoin(
            MediaPersonLink, join_cond
        ).outerjoin(
            MetadataMatch, MediaPersonLink.match_id == MetadataMatch.id
        )
        
        if role == "Actor":
            query = query.filter((MediaPersonLink.role == RoleType.ACTOR) | (Person.known_for_department == "Acting"))
        elif role == "Director":
            query = query.filter((MediaPersonLink.role == RoleType.DIRECTOR) | (Person.known_for_department.in_(["Directing", "Creator"])))
        elif role == "Writer":
            query = query.filter((MediaPersonLink.role == RoleType.WRITER) | (Person.known_for_department == "Writing"))
            
        if gender == "female":
            query = query.filter(Person.gender == 1)
        elif gender == "male":
            query = query.filter(Person.gender == 2)

        if adult_only:
            query = query.filter(Person.is_adult == True)
        else:
            query = query.filter(Person.is_adult == False)

        query = query.group_by(Person.id)
        results = query.all()
        
        people_list = []
        for person, library_count, linked_adult_flag in results:
            if not include_inactive and not person.is_active:
                continue
            if include_inactive and not person.is_active and library_count == 0:
                continue
            
            # Simple title search
            if search and search.lower() not in person.name.lower():
                continue
                
            people_list.append({
                "id": person.id,
                "name": person.name,
                "profile_path": self._resolve_img(person.profile_path, "people"),
                "gender": person.gender,
                "scene_count": person.scene_count,
                "rating_porndb": person.rating_porndb,
                "popularity": person.popularity or 0.0,
                "popularity_score": (
                    person.rating_porndb
                    if person.is_adult and person.rating_porndb is not None
                    else person.popularity or 0.0
                ),
                "is_adult": person.is_adult,
                "is_active": person.is_active,
                "library_count": library_count,
                "known_for": person.known_for_department
            })
            
        # Sorting
        if sort_by in ("library_count", "library_count_desc"):
            people_list.sort(key=lambda x: (-x["library_count"], -x["popularity_score"]))
        elif sort_by == "library_count_asc":
            people_list.sort(key=lambda x: (x["library_count"], x["popularity_score"]))
        elif sort_by in ("popularity", "popularity_desc"):
            people_list.sort(key=lambda x: (-x["popularity_score"], -x["library_count"]))
        elif sort_by == "popularity_asc":
            people_list.sort(key=lambda x: (x["popularity_score"], x["library_count"]))
        elif sort_by in ("name", "name_asc", "title_asc"):
            people_list.sort(key=lambda x: x["name"].lower())
        elif sort_by in ("name_desc", "title_desc"):
            people_list.sort(key=lambda x: x["name"].lower(), reverse=True)
            
        total = len(people_list)
        for item in people_list:
            item.pop("popularity_score", None)
        sliced_list = people_list[offset:offset+limit]
        has_more = offset + len(sliced_list) < total
        
        return {
            "items": sliced_list,
            "total": total,
            "has_more": has_more,
            "offset": offset,
            "limit": limit
        }

    def get_person_detail(self, person_id: int):
        db = self.db
        person = db.query(Person).options(joinedload(Person.localizations)).filter(Person.id == person_id).first()
        if not person:
            return JSONResponse(status_code=404, content={"error": "Person not found"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        loc = LanguageService.get_best_localization(person.localizations, ui_lang)
        
        # Load credits linked to this person
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
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
                "type": item.item_type.value,
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            }
            
            if item.item_type in (MediaType.SCENE, MediaType.JAV):
                scenes.append(credit_entry)
            elif item.item_type == MediaType.MOVIE:
                movies.append(credit_entry)
            elif item.item_type in (MediaType.TV, MediaType.EPISODE):
                sid = match.parent_id or match.id
                if sid not in tv_map:
                    tv_map[sid] = credit_entry
        
        tv = list(tv_map.values())
        
        # Dynamically enrich from TMDB if tmdb_id is available and we lack images/biography
        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id and str(person_id).isdigit() and person_id < 100000000:
            tmdb_id = person_id
            
        if tmdb_id and (not loc or not person.images):
            try:
                tmdb_details = self.tmdb.get_person_details(int(tmdb_id), language=ui_lang)
                if tmdb_details:
                    person.birthday = tmdb_details.get("birthday") or person.birthday
                    person.place_of_birth = tmdb_details.get("place_of_birth") or person.place_of_birth
                    person.deathday = tmdb_details.get("deathday") or person.deathday
                    person.profile_path = tmdb_details.get("profile_path") or person.profile_path
                    if tmdb_details.get("images", {}).get("profiles"):
                        person.images = [p.get("file_path") for p in tmdb_details["images"]["profiles"]]
                    if tmdb_details.get("biography"):
                        # save localization
                        if not loc:
                            loc = PersonLocalization(person_id=person.id, locale=ui_lang, biography=tmdb_details["biography"])
                            db.add(loc)
                        else:
                            loc.biography = tmdb_details["biography"]
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to dynamically enrich person {person_id}: {e}")
        
        result = {
            "id": person.id,
            "name": person.name,
            "alternate_names": person.aliases or [],
            "biography": loc.biography if loc else None,
            "birthday": person.birthday,
            "deathday": person.deathday,
            "place_of_birth": person.place_of_birth,
            "gender": person.gender,
            "popularity": person.popularity or 0.0,
            "scene_count": person.scene_count,
            "rating_porndb": person.rating_porndb,
            "known_for_department": person.known_for_department,
            "is_adult": person.is_adult,
            "profile_path": self._resolve_img(person.profile_path, "people"),
            "backdrop_path": None,
            "is_active": person.is_active,
            "external_ids": person.external_ids or {},
            "images": [self._resolve_img(img, "people") for img in (person.images or [])],
            "known_for": movies[:4],
            "total_movie_credits": len(movies),
            "total_tv_credits": len(tv),
            "total_scene_credits": len(scenes),
            "initial_movie_credits_page": {"items": movies[:12], "page": 1, "page_size": 12, "total_items": len(movies), "total_pages": 1},
            "initial_tv_credits_page": {"items": tv[:12], "page": 1, "page_size": 12, "total_items": len(tv), "total_pages": 1},
            "initial_scene_credits_page": {"items": scenes[:12], "page": 1, "page_size": 12, "total_items": len(scenes), "total_pages": 1},
        }
        return JSONResponse(content=result)

    def get_person_movies(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return JSONResponse(status_code=404, content={"error": "Person not found"})
        
        # Load movie credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type == MediaType.MOVIE,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
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
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
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
        
        return JSONResponse(content={
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        })

    def get_person_tv(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return JSONResponse(status_code=404, content={"error": "Person not found"})
        
        # Load tv credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE]),
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
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
                    "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
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
        
        return JSONResponse(content={
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        })

    def get_person_scenes(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return JSONResponse(status_code=404, content={"error": "Person not found"})
        
        # Load scene credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type.in_([MediaType.SCENE, MediaType.JAV]),
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
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
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
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
        
        return JSONResponse(content={
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        })
