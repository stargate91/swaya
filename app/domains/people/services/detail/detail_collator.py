import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider
from app.domains.people.models import Person, PersonLocalization, ExternalSourceLink
from app.shared_kernel.language import LanguageService
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_service_port import ImageServicePort
from app.domains.people.services.filmography_service import FilmographyService
from app.domains.people.schemas import PersonDetailResponse
from app.domains.people.helpers import merge_images
from app.domains.people.services.detail.performer_stats_calculator import PerformerStatsCalculator
from app.domains.people.services.detail.profile_merger import ProfileMerger

logger = logging.getLogger(__name__)

class PersonDetailCollator:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort, tmdb: Any, library_port: LibraryPort, image_service: ImageServicePort, filmography_service: FilmographyService):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = tmdb
        self.library_port = library_port
        self.image_service = image_service
        self.filmography_service = filmography_service
        self.stats_calculator = PerformerStatsCalculator()
        self.profile_merger = ProfileMerger()

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

    def get_person_detail(self, person: Person, user_id: int, ui_lang: str) -> PersonDetailResponse:
        """Collates database objects, overrides, statistics, and scraper details to assemble a performer's profile."""
        db = self.db
        person = db.merge(person)
        person_id = person.id
        override_dict = self.library_port.get_person_user_override(user_id, person_id)
        
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
                    person = db.merge(person)
            except Exception as e:
                logger.error(f"Failed to dynamically enrich person {person_id}: {e}")
        if person.is_adult:
            links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
            has_been_enriched = len(links) > 0 or person.hair_color is not None or person.eye_color is not None
            if not has_been_enriched:
                try:
                    from app.domains.people.services.people_enricher import PeopleEnricher
                    enricher = PeopleEnricher(db, scrapers=self.scrapers)
                    
                    ext_ids = person.external_ids or {}
                    link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
                    
                    for prov_name, ext_id in ext_ids.items():
                        try:
                             prov = Provider(prov_name.lower())
                             if not any(ld["provider"] == prov for ld in link_data):
                                 link_data.append({"provider": prov, "external_id": str(ext_id)})
                        except Exception as e:
                             logger.debug(f"Swallowed exception: {e}", exc_info=True)
    
                    fetched_data = enricher.fetch_external_details(person.name, ext_ids, link_data, is_adult=True)
                    if fetched_data:
                        enricher.apply_enriched_data(person, fetched_data)
                        db.commit()
                        person = db.merge(person)
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

        effective_backdrop, source_tmdb_id, source_media_type = self.profile_merger.resolve_effective_backdrop(
            db=self.db,
            tmdb_client=self.tmdb,
            person=person,
            override_dict=override_dict,
            known_for=known_for,
            ui_lang=ui_lang
        )

        external_ids = self.profile_merger.build_external_ids(person)
        suggested_tags = self.profile_merger.build_suggested_tags(person)
        stats = self.stats_calculator.format_credits_stats(movies, tv, scenes)

        result = {
            "id": person.id,
            "suggested_tags": suggested_tags,
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
            "profile_path": self._resolve_img((override_dict.get("custom_poster") if override_dict and override_dict.get("custom_poster") else (person.local_profile_path or person.profile_path)), "people"),
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
            **stats,
            "external_links": [],
            "primary_provider": person.primary_provider.value if person.primary_provider else None,
            "field_routing": person.field_routing
        }

        result["external_links"] = self.profile_merger.build_external_links(person, external_ids)
        return PersonDetailResponse(**result)
