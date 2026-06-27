import logging
import math
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.shared_kernel.enums import Provider, MediaType
from app.domains.people.models import Person, PersonLocalization, ExternalSourceLink
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.user_context import get_current_user_id
from app.shared_kernel.ports.library_port import LibraryPort
from app.domains.people.services.filmography_service import FilmographyService
from app.application.people.schemas import (
    PeopleSearchResponse,
    PersonDetailResponse,
    PersonFilmographyResponse,
)
from app.shared_kernel.ports.image_service_port import ImageServicePort
from app.domains.people.helpers import merge_images

# Import new components
from app.domains.people.services.people_query import PeopleQueryBuilder
from app.domains.people.services.people_search_service import PeopleSearchService

logger = logging.getLogger(__name__)

class PerformerDetailReader:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort, library_port: LibraryPort, image_service: ImageServicePort, filmography_service: FilmographyService):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = scrapers.tmdb(db)
        self.library_port = library_port
        self.image_service = image_service
        self.filmography_service = filmography_service

        # Instantiate helper services
        self.query_builder = PeopleQueryBuilder(db, library_port, image_service)
        self.search_service = PeopleSearchService(db, scrapers, library_port, image_service)

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

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
    ) -> PeopleSearchResponse:
        return self.query_builder.get_people(
            search=search,
            role=role,
            sort_by=sort_by,
            include_inactive=include_inactive,
            adult_only=adult_only,
            gender=gender,
            offset=offset,
            limit=limit,
        )

    def _resolve_person(self, person_id: Any, load_localizations: bool = False) -> Person:
        db = self.db
        query = db.query(Person)
        if load_localizations:
            query = query.options(joinedload(Person.localizations))
        
        person = None
        person_id_str = str(person_id)
        if person_id_str.startswith("local:"):
            try:
                p_id = int(person_id_str.split(":", 1)[1])
                person = query.filter(Person.id == p_id).first()
            except (ValueError, TypeError):
                pass
        elif ":" not in person_id_str:
            try:
                p_id = int(person_id_str)
                person = query.filter(Person.id == p_id).first()
            except (ValueError, TypeError):
                pass
        
        if not person:
            if ":" in person_id_str and not person_id_str.startswith("local:"):
                parts = person_id_str.split(":", 1)
                source_name = parts[0]
                uuid_str = parts[1]
                scraper_name = "porndb" if source_name == "theporndb" else source_name
                if scraper_name == "stash":
                    scraper_name = "stashdb"
                try:
                    provider_enum = Provider(scraper_name)
                    link = db.query(ExternalSourceLink).filter(
                        ExternalSourceLink.provider == provider_enum,
                        ExternalSourceLink.external_id == uuid_str
                    ).first()
                    if link:
                        person = link.person
                        if load_localizations:
                            person = query.filter(Person.id == person.id).first()
                except Exception:
                    pass
            else:
                query_ext = db.query(Person)
                if load_localizations:
                    query_ext = query_ext.options(joinedload(Person.localizations))
                person = query_ext.filter(
                    Person.external_ids["tmdb"].as_string() == person_id_str
                ).first()
            
            if not person:
                try:
                    res = self.add_person_tmdb(str(person_id))
                    if res and res.get("status") == "success":
                        query_new = db.query(Person)
                        if load_localizations:
                            query_new = query_new.options(joinedload(Person.localizations))
                        person = query_new.filter(Person.id == res["id"]).first()
                except Exception as e:
                    logger.error(f"Error dynamically importing person {person_id}: {e}")
                    
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        return person

    def get_person_detail(self, person_id: Any) -> PersonDetailResponse:
        db = self.db
        person = self._resolve_person(person_id, load_localizations=True)
        person_id = person.id
        user_id = get_current_user_id() or 1
        override_dict = self.library_port.get_person_user_override(user_id, person_id)
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        loc = LanguageService.get_best_localization(person.localizations, ui_lang)

        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id:
            for link in person.external_links:
                if link.provider.value == "tmdb":
                    tmdb_id = link.external_id
                    break
        if not tmdb_id and not person.is_adult and str(person_id).isdigit() and person_id < 100000000:
            tmdb_id = person_id
            
        if tmdb_id:
            try:
                tmdb_details = self.tmdb.get_person_details(int(tmdb_id), language=ui_lang)
                if tmdb_details:
                    person.birthday = tmdb_details.get("birthday") or person.birthday
                    person.place_of_birth = tmdb_details.get("place_of_birth") or person.place_of_birth
                    person.deathday = tmdb_details.get("deathday") or person.deathday
                    person.profile_path = tmdb_details.get("profile_path") or person.profile_path
                    person.known_for_department = tmdb_details.get("known_for_department") or person.known_for_department
                    person.homepage = tmdb_details.get("homepage") or person.homepage
                    
                    if tmdb_details.get("also_known_as"):
                        aliases = list(person.aliases or [])
                        for alias in tmdb_details["also_known_as"]:
                            if alias not in aliases:
                                aliases.append(alias)
                        person.aliases = aliases
                    
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
                    if tmdb_id and current_ids.get("tmdb") != str(tmdb_id):
                        current_ids["tmdb"] = str(tmdb_id)
                        current_ids["tmdb_id"] = str(tmdb_id)
                        updated = True
                    if updated:
                        person.external_ids = current_ids

                    db.commit()
            except Exception as e:
                logger.error(f"Failed to dynamically enrich person {person_id}: {e}")
        if person.is_adult:
            try:
                from app.domains.people.services.people_enricher import PeopleEnricher
                enricher = PeopleEnricher(db, scrapers=self.scrapers)
                
                ext_ids = person.external_ids or {}
                links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
                link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
                
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
        source_tmdb_id = None
        source_media_type = None
        if override_dict and override_dict.get("custom_backdrop"):
            effective_backdrop = override_dict.get("custom_backdrop")
        elif tmdb_id:
            from app.domains.people.helpers import resolve_person_known_for_backdrop
            effective_backdrop, source_tmdb_id, source_media_type = resolve_person_known_for_backdrop(
                db,
                self.tmdb,
                known_for,
                [ui_lang],
                department=person.known_for_department,
                adult_only=person.is_adult,
                respect_credit_order=True
            )

        external_ids = dict(person.external_ids or {})
        for link in person.external_links:
            prov_key = link.provider.value
            if prov_key not in external_ids:
                external_ids[prov_key] = link.external_id
            alt_key = f"{prov_key}_id" if prov_key != "porndb" else "theporndb_id"
            if alt_key not in external_ids:
                external_ids[alt_key] = link.external_id
        if "tmdb" in external_ids and "tmdb_id" not in external_ids:
            external_ids["tmdb_id"] = external_ids["tmdb"]
        if "stashdb" in external_ids and "stashdb_id" not in external_ids:
            external_ids["stashdb_id"] = external_ids["stashdb"]
        if "porndb" in external_ids and "theporndb_id" not in external_ids:
            external_ids["theporndb_id"] = external_ids["porndb"]
        if "fansdb" in external_ids and "fansdb_id" not in external_ids:
            external_ids["fansdb_id"] = external_ids["fansdb"]
        
        if person.socials:
            for k, v in person.socials.items():
                if v and f"{k}_id" not in external_ids:
                    external_ids[f"{k}_id"] = v
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
                "band_size": person.band_size,
                "waist": person.waist,
                "hip": person.hip,
                "breast_type": person.breast_type,
                "tattoos": person.tattoos,
                "piercings": person.piercings,
                "same_sex_only": person.same_sex_only,
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
            "profile_path": self._resolve_img((override_dict.get("custom_poster") if override_dict and override_dict.get("custom_poster") else person.profile_path), "people"),
            "backdrop_path": self._resolve_img(effective_backdrop, "backdrops", size="original"),
            "backdrop_source_tmdb_id": source_tmdb_id,
            "backdrop_source_media_type": source_media_type,
            "is_active": person.is_active,
            "is_favorite": override_dict.get("is_favorite") if override_dict else False,
            "user_rating": override_dict.get("user_rating") if override_dict else None,
            "user_comment": override_dict.get("user_comment") if override_dict else None,
            "homepage": person.homepage,
            "external_ids": external_ids,
            "images": [self._resolve_img(img, "people") for img in (person.images or [])],
            "hair_color": person.hair_color,
            "eye_color": person.eye_color,
            "ethnicity": person.ethnicity,
            "height": person.height,
            "weight": person.weight,
            "measurements": person.measurements,
            "cup_size": person.cup_size,
            "band_size": person.band_size,
            "waist": person.waist,
            "hip": person.hip,
            "breast_type": person.breast_type,
            "tattoos": person.tattoos,
            "piercings": person.piercings,
            "same_sex_only": person.same_sex_only,
            "socials": person.socials or {},
            "career_start_year": person.career_start_year,
            "career_end_year": person.career_end_year,
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
            "external_links": [
                {
                    "provider": link.provider.value,
                    "external_id": link.external_id,
                    "profile_url": link.profile_url,
                    "source_data": link.source_data
                }
                for link in person.external_links
            ],
            "primary_provider": person.primary_provider.value if person.primary_provider else None,
            "field_routing": person.field_routing
        }
        return PersonDetailResponse(**result)

    def get_person_movies(self, person_id: Any, page: int = 1, page_size: int = 12, source: Optional[str] = None) -> PersonFilmographyResponse:
        db = self.db
        person = self._resolve_person(person_id)
        person_id = person.id
        
        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id:
            for link in person.external_links:
                if link.provider.value == "tmdb":
                    tmdb_id = link.external_id
                    break
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
        
        if source and source.lower() != "tmdb":
            res = self.filmography_service.get_person_movies(person_id, page, page_size, source)
            return PersonFilmographyResponse(**res)

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

    def get_person_tv(self, person_id: Any, page: int = 1, page_size: int = 12) -> PersonFilmographyResponse:
        db = self.db
        person = self._resolve_person(person_id)
        person_id = person.id

        ext_ids = person.external_ids or {}
        tmdb_id = ext_ids.get("tmdb") or ext_ids.get("tmdb_id")
        if not tmdb_id:
            for link in person.external_links:
                if link.provider.value == "tmdb":
                    tmdb_id = link.external_id
                    break
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

    def get_person_scenes(self, person_id: Any, page: int = 1, page_size: int = 12, source: Optional[str] = None) -> PersonFilmographyResponse:
        db = self.db
        person = self._resolve_person(person_id)
        person_id = person.id
        res = self.filmography_service.get_person_scenes(person_id, page, page_size, source)
        return PersonFilmographyResponse(**res)

    def get_person_credit_backdrops(self, person_id: Any, tmdb_id: int, media_type: str) -> Dict[str, Any]:
        db = self.db
        person = self._resolve_person(person_id)
        person_id = person.id

        normalized_type = "tv" if str(media_type or "").lower() in {"tv", "series"} else "movie"
        ui_lang = DEFAULT_FALLBACK_LANGUAGE

        raw_data = self.tmdb.get_details(tmdb_id, normalized_type, language=ui_lang, include_images=True, append_parts=["images"])
        backdrops = ((raw_data or {}).get("images") or {}).get("backdrops") or []
        has_valid_backdrops = any((not bd.get("iso_639_1") or bd.get("iso_639_1") == "") and int(bd.get("width") or 0) >= 1280 for bd in backdrops)

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

    def search_people_tmdb(self, query: str, language: Optional[str] = None, adult_only: bool = False, page: int = 1, source: str = "all") -> List[Dict[str, Any]]:
        return self.search_service.search_people_tmdb(
            query=query,
            language=language,
            adult_only=adult_only,
            page=page,
            source=source,
        )

    def add_person_tmdb(
        self,
        db_id_or_external: str,
        name: Optional[str] = None,
        profile_path: Optional[str] = None,
        gender: Optional[int] = None,
        is_adult: Optional[bool] = None,
        is_active: bool = False
    ) -> Dict[str, Any]:
        return self.search_service.add_person_tmdb(
            db_id_or_external=db_id_or_external,
            name=name,
            profile_path=profile_path,
            gender=gender,
            is_adult=is_adult,
            is_active=is_active,
        )
