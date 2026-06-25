import logging
import math
from typing import Optional, List, Dict, Any
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.shared_kernel.enums import MediaType, ItemStatus, RoleType, Provider
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import Person, PersonLocalization, MediaPersonLink, ExternalSourceLink
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.user_context import get_current_user_id
from app.domains.people.services.filmography_service import FilmographyService
from app.domains.people.schemas import (
    PeopleSearchResponse,
    PersonDetailResponse,
    PersonFilmographyResponse,
)

from app.domains.media_assets.services.images import image_processing_service

logger = logging.getLogger(__name__)

class PeopleDetailService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = scrapers.tmdb(db)
        self.filmography_service = FilmographyService(db)

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return image_processing_service.resolve_image_url(path, subfolder, size)


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
        
        statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]

        # Determine target match IDs linked to library items
        matched_match_ids = [
            m.id for m in db.query(MetadataMatch).join(MediaItem).filter(
                MediaItem.status.in_(statuses)
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
            else_=MetadataMatch.id
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
                
            # Populate normalized external_ids like in detail view
            external_ids = dict(person.external_ids or {})
            if "tmdb" in external_ids and "tmdb_id" not in external_ids:
                external_ids["tmdb_id"] = external_ids["tmdb"]
            if "stashdb" in external_ids and "stashdb_id" not in external_ids:
                external_ids["stashdb_id"] = external_ids["stashdb"]
            if "porndb" in external_ids and "theporndb_id" not in external_ids:
                external_ids["theporndb_id"] = external_ids["porndb"]
            if "fansdb" in external_ids and "fansdb_id" not in external_ids:
                external_ids["fansdb_id"] = external_ids["fansdb"]

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
                "known_for": person.known_for_department,
                "external_ids": external_ids
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
        
        return PeopleSearchResponse(
            items=sliced_list,
            total=total,
            has_more=has_more,
            offset=offset,
            limit=limit
        )

    def get_person_detail(self, person_id: int) -> PersonDetailResponse:
        db = self.db
        person = db.query(Person).options(joinedload(Person.localizations)).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        from app.domains.users.models import UserOverride

        user_id = get_current_user_id() or 1
        override = db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person_id
        ).first()
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        loc = LanguageService.get_best_localization(person.localizations, ui_lang)
        
        def merge_images(existing: Optional[List[str]], new_images: List[str]) -> List[str]:
            if not existing:
                existing = []
            seen = set()
            res_list = []
            for img in existing:
                if not img:
                    continue
                norm = img.split("/")[-1].split("?")[0].lower()
                if norm not in seen:
                    seen.add(norm)
                    res_list.append(img)
            for img in new_images:
                if not img:
                    continue
                norm = img.split("/")[-1].split("?")[0].lower()
                if norm not in seen:
                    seen.add(norm)
                    res_list.append(img)
            return res_list

        # Dynamically enrich from TMDB if tmdb_id is available and we lack images/biography
        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id and not person.is_adult and str(person_id).isdigit() and person_id < 100000000:
            tmdb_id = person_id
            
        # Dynamically enrich from TMDB if tmdb_id is available and we lack images/biography OR lack social links (like instagram_id)
        if tmdb_id:
            try:
                tmdb_details = self.tmdb.get_person_details(int(tmdb_id), language=ui_lang)
                if tmdb_details:
                    person.birthday = tmdb_details.get("birthday") or person.birthday
                    person.place_of_birth = tmdb_details.get("place_of_birth") or person.place_of_birth
                    person.deathday = tmdb_details.get("deathday") or person.deathday
                    person.profile_path = tmdb_details.get("profile_path") or person.profile_path
                    person.known_for_department = tmdb_details.get("known_for_department") or person.known_for_department
                    
                    profiles = tmdb_details.get("images", {}).get("profiles") or []
                    new_imgs = [p.get("file_path") for p in profiles if p.get("file_path")]
                    if person.profile_path:
                        new_imgs.insert(0, person.profile_path)
                    person.images = merge_images(person.images, new_imgs)
                    
                    if tmdb_details.get("biography"):
                        if not loc:
                            loc = PersonLocalization(person_id=person.id, locale=ui_lang, biography=tmdb_details["biography"])
                            db.add(loc)
                        else:
                            loc.biography = tmdb_details["biography"]
                    
                    ext_ids_from_tmdb = tmdb_details.get("external_ids") or {}
                    imdb_id_from_tmdb = tmdb_details.get("imdb_id") or ext_ids_from_tmdb.get("imdb_id")
                    current_ids = dict(person.external_ids or {})
                    updated = False
                    if imdb_id_from_tmdb and current_ids.get("imdb_id") != imdb_id_from_tmdb:
                        current_ids["imdb_id"] = imdb_id_from_tmdb
                        updated = True
                    for key in ["facebook_id", "instagram_id", "twitter_id"]:
                        val = ext_ids_from_tmdb.get(key)
                        if val and current_ids.get(key) != val:
                            current_ids[key] = val
                            updated = True
                    if updated:
                        person.external_ids = current_ids

                    db.commit()
            except Exception as e:
                logger.error(f"Failed to dynamically enrich person {person_id}: {e}")
        elif person.is_adult:
            try:
                from app.domains.people.services.people_enricher import PeopleEnricher
                enricher = PeopleEnricher(db, scrapers=self.scrapers)
                
                # Gather links
                links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
                link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
                
                # Also check external_ids JSON field
                for prov_name, ext_id in ext_ids.items():
                    try:
                         prov = Provider(prov_name.lower())
                         if not any(ld["provider"] == prov for ld in link_data):
                             link_data.append({"provider": prov, "external_id": str(ext_id)})
                    except Exception:
                         pass

                
                fetched_data = enricher.fetch_external_details(person.name, ext_ids, link_data, is_adult=True)
                if fetched_data:
                    enricher.apply_enriched_data(person, fetched_data)
                    db.commit()
                    db.refresh(person)
                    loc = LanguageService.get_best_localization(person.localizations, ui_lang)
            except Exception as e:
                logger.error(f"Failed to dynamically enrich adult performer {person_id}: {e}", exc_info=True)
        
        # Delegate combined credits lookup to FilmographyService
        movies, tv, scenes, known_for = self.filmography_service.get_combined_filmography(
            person_id,
            tmdb_id=tmdb_id,
            ui_lang=ui_lang,
            tmdb_client=self.tmdb,
            is_adult=person.is_adult,
            known_for_department=person.known_for_department,
            person_name=person.name
        )

        effective_backdrop = None
        if override and override.custom_backdrop:
            effective_backdrop = override.custom_backdrop
        elif not person.is_adult and tmdb_id:
            from app.domains.people.helpers import resolve_person_known_for_backdrop
            effective_backdrop = resolve_person_known_for_backdrop(
                db,
                self.tmdb,
                known_for,
                [ui_lang],
                department=person.known_for_department,
                adult_only=person.is_adult,
                respect_credit_order=True
            )

        external_ids = dict(person.external_ids or {})
        if "tmdb" in external_ids and "tmdb_id" not in external_ids:
            external_ids["tmdb_id"] = external_ids["tmdb"]
        if "stashdb" in external_ids and "stashdb_id" not in external_ids:
            external_ids["stashdb_id"] = external_ids["stashdb"]
        if "porndb" in external_ids and "theporndb_id" not in external_ids:
            external_ids["theporndb_id"] = external_ids["porndb"]
        if "fansdb" in external_ids and "fansdb_id" not in external_ids:
            external_ids["fansdb_id"] = external_ids["fansdb"]
        
        # Merge socials from person.socials or person.external_ids if they exist
        if person.socials:
            for k, v in person.socials.items():
                if v and f"{k}_id" not in external_ids:
                    external_ids[f"{k}_id"] = v
        # Ensure fallback for imdb_id vs imdb
        if "imdb" in external_ids and "imdb_id" not in external_ids:
            external_ids["imdb_id"] = external_ids["imdb"]
        elif "imdb_id" in external_ids and "imdb" not in external_ids:
            external_ids["imdb"] = external_ids["imdb_id"]
        external_ids["attributes"] = {
            **dict(external_ids.get("attributes") or {}),
            **({
                "hair_color": person.hair_color,
                "eye_color": person.eye_color,
                "ethnicity": person.ethnicity,
                "height": person.height,
                "weight": person.weight,
                "measurements": person.measurements,
                "cup_size": person.cup_size,
                "tattoos": person.tattoos,
                "piercings": person.piercings,
                "orientation": person.orientation,
            }),
        }
        external_ids["attributes"] = {
            key: value for key, value in external_ids["attributes"].items()
            if value not in (None, "", [], {})
        }

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
            "profile_path": self._resolve_img((override.custom_poster if override and override.custom_poster else person.profile_path), "people"),
            "backdrop_path": self._resolve_img(effective_backdrop, "backdrops", size="original"),
            "is_active": person.is_active,
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "external_ids": external_ids,
            "images": [self._resolve_img(img, "people") for img in (person.images or [])],
            "hair_color": person.hair_color,
            "eye_color": person.eye_color,
            "ethnicity": person.ethnicity,
            "height": person.height,
            "weight": person.weight,
            "measurements": person.measurements,
            "cup_size": person.cup_size,
            "tattoos": person.tattoos,
            "piercings": person.piercings,
            "orientation": person.orientation,
            "socials": person.socials or {},
            "known_for": [
                {
                    **item,
                    "poster_path": self._resolve_img(item.get("poster_path"), "posters") if item.get("poster_path") else None,
                    "backdrop_path": self._resolve_img(item.get("backdrop_path"), "backdrops", size="original") if item.get("backdrop_path") else None,
                }
                for item in known_for[:8]
            ],
            "total_movie_credits": len(movies),
            "total_tv_credits": len(tv),
            "total_scene_credits": len(scenes),
            "initial_movie_credits_page": {"items": movies[:12], "page": 1, "page_size": 12, "total_items": len(movies), "total_pages": 1},
            "initial_tv_credits_page": {"items": tv[:12], "page": 1, "page_size": 12, "total_items": len(tv), "total_pages": 1},
            "initial_scene_credits_page": {"items": scenes[:12], "page": 1, "page_size": 12, "total_items": len(scenes), "total_pages": 1},
        }
        return PersonDetailResponse(**result)

    def get_person_movies(self, person_id: int, page: int = 1, page_size: int = 12) -> PersonFilmographyResponse:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        
        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id and not person.is_adult and str(person_id).isdigit() and person_id < 100000000:
            tmdb_id = person_id

        movies, _, _, _ = self.filmography_service.get_combined_filmography(
            person_id,
            tmdb_id=tmdb_id,
            ui_lang=DEFAULT_FALLBACK_LANGUAGE,
            tmdb_client=self.tmdb,
            is_adult=person.is_adult,
            known_for_department=person.known_for_department,
            person_name=person.name
        )
        
        total_items = len(movies)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = movies[start_idx : start_idx + page_size]
        
        res = {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }
        return PersonFilmographyResponse(**res)

    def get_person_tv(self, person_id: int, page: int = 1, page_size: int = 12) -> PersonFilmographyResponse:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id and not person.is_adult and str(person_id).isdigit() and person_id < 100000000:
            tmdb_id = person_id

        _, tv, _, _ = self.filmography_service.get_combined_filmography(
            person_id,
            tmdb_id=tmdb_id,
            ui_lang=DEFAULT_FALLBACK_LANGUAGE,
            tmdb_client=self.tmdb,
            is_adult=person.is_adult,
            known_for_department=person.known_for_department,
            person_name=person.name
        )
        
        total_items = len(tv)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = tv[start_idx : start_idx + page_size]
        
        res = {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }
        return PersonFilmographyResponse(**res)

    def get_person_scenes(self, person_id: int, page: int = 1, page_size: int = 12) -> PersonFilmographyResponse:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        res = self.filmography_service.get_person_scenes(person_id, page, page_size)
        return PersonFilmographyResponse(**res)

    def get_person_credit_backdrops(self, person_id: int, tmdb_id: int, media_type: str) -> Dict[str, Any]:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        normalized_type = "tv" if str(media_type or "").lower() in {"tv", "series"} else "movie"
        ui_lang = DEFAULT_FALLBACK_LANGUAGE

        raw_data = self.tmdb.get_details(tmdb_id, normalized_type, language=ui_lang, include_images=True, append_parts=["images"])
        backdrops = ((raw_data or {}).get("images") or {}).get("backdrops") or []
        has_valid_backdrops = any((not bd.get("iso_639_1") or bd.get("iso_639_1") == "") and int(bd.get("width") or 0) >= 1280 for bd in backdrops)

        # Resolve backdrop paths for frontend
        resolved_backdrops = []
        for bd in backdrops:
            resolved_bd = dict(bd)
            resolved_bd["file_path"] = self._resolve_img(bd.get("file_path"), "backdrops", size="original")
            resolved_backdrops.append(resolved_bd)

        return {
            "tmdb_id": tmdb_id,
            "media_type": normalized_type,
            "title": raw_data.get("title") or raw_data.get("name") or raw_data.get("original_title") or raw_data.get("original_name"),
            "backdrops": resolved_backdrops,
            "has_valid_backdrops": has_valid_backdrops,
        }

    def update_person_backdrop(self, person_id: int, backdrop_path: str) -> Dict[str, Any]:
        from app.domains.users.models import UserOverride
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1
        override = db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person_id
        ).first()
        if not override:
            override = UserOverride(user_id=user_id, person_id=person_id)
            db.add(override)

        override.custom_backdrop = backdrop_path
        db.commit()

        # Mark person as active on user interaction
        person.is_active = True
        db.commit()

        return {
            "status": "success",
            "backdrop_path": self._resolve_img(backdrop_path, "backdrops", size="original"),
            "has_local_backdrop": bool(backdrop_path)
        }

    def handle_person_backdrop_upload(self, person_id: int, filename: str, file_stream) -> Dict[str, Any]:
        import os
        import uuid
        from app.domains.users.models import UserOverride
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1
        override = db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person_id
        ).first()
        if not override:
            override = UserOverride(user_id=user_id, person_id=person_id)
            db.add(override)

        img_service = image_processing_service
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path("backdrops", new_filename)
        thumbnail_path = img_service.get_thumbnail_path("backdrops", new_filename)

        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            raise HTTPException(status_code=400, detail="Failed to save uploaded image")

        img_service.generate_thumbnail(original_path, thumbnail_path, "backdrops")

        override.custom_backdrop = new_filename
        person.is_active = True
        db.commit()

        resolved_url = img_service.resolve_image_url(new_filename, "backdrops", size="original")
        return {"status": "success", "backdrop_path": resolved_url, "has_local_backdrop": True}

    def update_person_profile(self, person_id: int, profile_path: str) -> Dict[str, Any]:
        from app.domains.users.models import UserOverride
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1
        override = db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person_id
        ).first()
        if not override:
            override = UserOverride(user_id=user_id, person_id=person_id)
            db.add(override)

        override.custom_poster = profile_path
        person.is_active = True
        db.commit()

        return {
            "status": "success",
            "profile_path": self._resolve_img(profile_path, "people"),
            "has_local_profile": bool(profile_path)
        }

    def handle_person_profile_upload(self, person_id: int, filename: str, file_stream) -> Dict[str, Any]:
        import os
        import uuid
        from app.domains.users.models import UserOverride
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1
        override = db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person_id
        ).first()
        if not override:
            override = UserOverride(user_id=user_id, person_id=person_id)
            db.add(override)

        img_service = image_processing_service
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path("people", new_filename)
        thumbnail_path = img_service.get_thumbnail_path("people", new_filename)

        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            raise HTTPException(status_code=400, detail="Failed to save uploaded image")

        img_service.generate_thumbnail(original_path, thumbnail_path, "people")

        override.custom_poster = new_filename
        person.is_active = True
        db.commit()

        resolved_url = img_service.resolve_image_url(new_filename, "people")
        return {"status": "success", "profile_path": resolved_url, "has_local_profile": True}

    def search_people_tmdb(self, query: str, language: Optional[str] = None, adult_only: bool = False, page: int = 1, source: str = "all") -> List[Dict[str, Any]]:
        db = self.db
        import hashlib
        from app.domains.users.models import UserOverride
        from app.domains.people.models import MediaPersonLink, Person
        from app.domains.library.models import MediaItem
        from app.domains.metadata.models import MetadataMatch
        from app.shared_kernel.enums import ItemStatus, Provider
        from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

        if not language:
            language = DEFAULT_FALLBACK_LANGUAGE

        page = max(1, int(page or 1))
        adult_results = []

        if adult_only and source != "tmdb":
            def get_stable_integer_id(src: str, u_str: str) -> int:
                h = hashlib.sha256(f"{src}:{u_str}".encode()).hexdigest()
                return int(h[:7], 16)

            sources_to_search = ["stashdb", "fansdb", "theporndb"] if source == "all" else [source]
            for source_name in sources_to_search:
                try:
                    scraper_name = "porndb" if source_name == "theporndb" else source_name
                    try:
                        provider_enum = Provider(scraper_name)
                        scraper_client = self.scrapers.adult(provider_enum, db)
                    except Exception:
                        scraper_client = None
                    if not scraper_client:
                        continue

                    performers = scraper_client.search_performers(query)
                    for perf in performers:
                        uuid_str = perf.get("id")
                        if not uuid_str:
                            continue

                        stable_id = get_stable_integer_id(source_name, uuid_str)

                        gender_str = str(perf.get("gender") or "").upper()
                        if "FEMALE" in gender_str:
                            mapped_gender = 1
                        elif "MALE" in gender_str:
                            mapped_gender = 2
                        elif gender_str:
                            mapped_gender = 3
                        else:
                            mapped_gender = 0

                        images = perf.get("images") or []
                        profile_url = images[0].get("url") if images else None

                        link = db.query(ExternalSourceLink).filter(
                            ExternalSourceLink.provider == provider_enum,
                            ExternalSourceLink.external_id == uuid_str
                        ).first()
                        person = link.person if link else None

                        is_linked = False
                        if person:
                            linked_rows = (
                                db.query(MediaPersonLink.person_id)
                                .join(MetadataMatch, MetadataMatch.id == MediaPersonLink.match_id)
                                .join(MediaItem, MediaItem.id == MetadataMatch.media_item_id)
                                .filter(
                                    MediaPersonLink.person_id == person.id,
                                    MetadataMatch.is_active.is_(True),
                                    MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED]),
                                )
                                .distinct()
                                .all()
                            )
                            is_linked = len(linked_rows) > 0

                        adult_results.append({
                            "id": f"{source_name}:{uuid_str}",
                            "name": perf.get("name"),
                            "adult": True,
                            "gender": mapped_gender,
                            "profile_path": profile_url,
                            "known_for_department": "Acting",
                            "known_for": [],
                            "is_active": bool(person.is_active) if person else False,
                            "is_pinned": False,  # Simplified or check override
                            "is_linked": is_linked
                        })
                except Exception as ex:
                    logger.error(f"Error searching {source_name}: {ex}")

            if source != "all":
                return adult_results

        # TMDB Search path
        seen_names = {r["name"].lower().strip() for r in adult_results}
        results = self.tmdb.search_person(query=query, language=language, include_adult=True, page=page)

        if adult_only:
            results = [r for r in (results or []) if bool(r.get("adult"))]

        person_ids = []
        for result in results:
            name = result.get("name")
            if not name or name.lower().strip() in seen_names:
                continue
            try:
                person_ids.append(int(result.get("id")))
            except (TypeError, ValueError):
                continue

        local_people = {}
        linked_person_ids = set()

        if person_ids:
            local_people = {
                person.id: person
                for person in db.query(Person).filter(Person.id.in_(person_ids)).all()
            }

            linked_rows = (
                db.query(MediaPersonLink.person_id)
                .join(MetadataMatch, MetadataMatch.id == MediaPersonLink.match_id)
                .join(MediaItem, MediaItem.id == MetadataMatch.media_item_id)
                .filter(
                    MediaPersonLink.person_id.in_(person_ids),
                    MetadataMatch.is_active.is_(True),
                    MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED]),
                )
                .distinct()
                .all()
            )
            linked_person_ids = {int(person_id) for (person_id,) in linked_rows if person_id is not None}

        for result in results:
            name = result.get("name")
            if not name or name.lower().strip() in seen_names:
                continue
            try:
                person_id = int(result.get("id"))
            except (TypeError, ValueError):
                continue

            local_person = local_people.get(person_id)
            mapped_gender = result.get("gender") or 0

            # Map known_for
            raw_known_for = result.get("known_for") or []
            known_for_list = []
            for item in raw_known_for:
                known_for_list.append({
                    "title": item.get("title") or item.get("name") or "Unknown",
                })

            adult_results.append({
                "id": person_id,
                "name": name,
                "adult": bool(result.get("adult")),
                "gender": mapped_gender,
                "profile_path": self._resolve_img(result.get("profile_path"), "people") if result.get("profile_path") else None,
                "known_for_department": result.get("known_for_department") or "Acting",
                "known_for": known_for_list,
                "is_active": bool(local_person.is_active) if local_person else False,
                "is_pinned": False,
                "is_linked": person_id in linked_person_ids
            })

        return adult_results

    def add_person_tmdb(
        self,
        db_id_or_external: str,
        name: Optional[str] = None,
        profile_path: Optional[str] = None,
        gender: Optional[int] = None,
        is_adult: Optional[bool] = None
    ) -> Dict[str, Any]:
        db = self.db
        from app.domains.people.services.person_service import PersonService
        from app.shared_kernel.enums import Provider
        import hashlib
        
        # Check if it's an adult performer ID (e.g. stashdb:uuid)
        if isinstance(db_id_or_external, str) and ":" in db_id_or_external:
            parts = db_id_or_external.split(":", 1)
            source_name = parts[0]
            uuid_str = parts[1]
            
            scraper_name = "porndb" if source_name == "theporndb" else source_name
            provider_enum = Provider(scraper_name)

            # Try to find locally first
            link = db.query(ExternalSourceLink).filter(
                ExternalSourceLink.provider == provider_enum,
                ExternalSourceLink.external_id == uuid_str
            ).first()
            if link and link.person:
                person = link.person
                person.is_active = True
                db.commit()
                return {"status": "success", "id": person.id, "name": person.name}

            scraper_client = self.scrapers.adult(provider_enum, db)
            if not scraper_client:
                raise HTTPException(status_code=400, detail=f"Provider {source_name} not available")
                
            perf = None
            try:
                perf = scraper_client.get_performer_details(uuid_str)
            except Exception as e:
                logger.error(f"Error fetching performer details from provider {source_name}: {e}")

            if not perf:
                if name:
                    perf = {
                        "name": name,
                        "images": [{"url": profile_path}] if profile_path else [],
                        "gender": "female" if gender == 1 else "male" if gender == 2 else "trans" if gender == 3 else None
                    }
                else:
                    raise HTTPException(status_code=404, detail="Performer not found on provider and no details provided")
                
            gender_str = str(perf.get("gender") or "").upper()
            if "FEMALE" in gender_str:
                mapped_gender = 1
            elif "MALE" in gender_str:
                mapped_gender = 2
            elif gender_str:
                mapped_gender = 3
            else:
                mapped_gender = 0
                
            images = perf.get("images") or []
            profile_url = images[0].get("url") if images else None
            
            service = PersonService(db)
            person = service.update_or_create_person(
                name=perf.get("name"),
                profile_path=profile_url,
                gender=mapped_gender,
                is_adult=True,
                provider=provider_enum,
                external_id=uuid_str,
                known_for_department="Acting"
            )
            
            person.is_active = True
            db.commit()
            return {"status": "success", "id": person.id, "name": person.name}
            
        else:
            # SFW TMDB path
            try:
                tmdb_id = int(db_id_or_external)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid person ID format")

            # Try to find locally first
            person = db.query(Person).filter(Person.external_ids["tmdb"] == str(tmdb_id)).first()
            if person:
                person.is_active = True
                db.commit()
                return {"status": "success", "id": person.id, "name": person.name}
                
            tmdb_details = None
            try:
                tmdb_details = self.tmdb.get_person_details(tmdb_id)
            except Exception as e:
                logger.error(f"Error fetching person details from TMDB: {e}")

            if not tmdb_details:
                if name:
                    tmdb_details = {
                        "name": name,
                        "profile_path": profile_path,
                        "gender": gender,
                        "known_for_department": "Acting"
                    }
                else:
                    raise HTTPException(status_code=404, detail="Person not found on TMDB and no details provided")
                
            service = PersonService(db)
            person = service.update_or_create_person(
                name=tmdb_details.get("name"),
                profile_path=tmdb_details.get("profile_path"),
                gender=tmdb_details.get("gender"),
                is_adult=False,
                tmdb_id=str(tmdb_id),
                known_for_department=tmdb_details.get("known_for_department") or "Acting"
            )
            
            person.is_active = True
            db.commit()
            return {"status": "success", "id": person.id, "name": person.name}



