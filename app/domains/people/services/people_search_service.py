import hashlib
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider
from app.domains.people.models import Person, ExternalSourceLink, MediaPersonLink
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class PeopleSearchService:
    def __init__(self, db: Session, scrapers: Any, library_port: Any, image_service: Any):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = scrapers.tmdb(db)
        self.library_port = library_port
        self.image_service = image_service

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

    def search_people_tmdb(self, query: str, language: Optional[str] = None, adult_only: bool = False, page: int = 1, source: str = "all") -> List[Dict[str, Any]]:
        db = self.db
        
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
                            active_match_ids = self.library_port.get_active_match_ids()
                            linked_rows = (
                                db.query(MediaPersonLink.person_id)
                                .filter(
                                    MediaPersonLink.person_id == person.id,
                                    MediaPersonLink.match_id.in_(active_match_ids),
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
                            "is_pinned": False,
                            "is_linked": is_linked
                        })
                except Exception as ex:
                    logger.error(f"Error searching {source_name}: {ex}")

            if source != "all":
                return adult_results

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
                for person in db.query(Person).filter(
                    (Person.id.in_(person_ids)) | 
                    (Person.external_ids["tmdb"].as_string().in_([str(pid) for pid in person_ids]))
                ).all()
            }

            active_match_ids = self.library_port.get_active_match_ids()
            linked_rows = (
                db.query(MediaPersonLink.person_id)
                .filter(
                    MediaPersonLink.person_id.in_(person_ids),
                    MediaPersonLink.match_id.in_(active_match_ids),
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
            if not local_person:
                local_person = next((p for p in local_people.values() if p.external_ids and p.external_ids.get("tmdb") == str(person_id)), None)

            mapped_gender = result.get("gender") or 0

            raw_known_for = result.get("known_for") or []
            known_for_list = []
            for item in raw_known_for:
                known_for_list.append({
                    "title": item.get("title") or item.get("name") or "Unknown",
                })

            is_linked = person_id in linked_person_ids
            if not is_linked and local_person:
                is_linked = local_person.id in linked_person_ids

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
                "is_linked": is_linked
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
        
        if isinstance(db_id_or_external, str) and ":" in db_id_or_external:
            parts = db_id_or_external.split(":", 1)
            source_name = parts[0]
            uuid_str = parts[1]
            
            scraper_name = "porndb" if source_name == "theporndb" else source_name
            provider_enum = Provider(scraper_name)

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
                known_for_department="Acting",
                urls=perf.get("urls")
            )
            
            person.is_active = True
            db.commit()
            return {"status": "success", "id": person.id, "name": person.name}
            
        else:
            try:
                tmdb_id = int(db_id_or_external)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid person ID format")

            person_query = db.query(Person).filter(Person.external_ids["tmdb"].as_string() == str(tmdb_id))
            if is_adult is not None:
                person = person_query.filter(Person.is_adult == is_adult).first()
            else:
                person = person_query.filter(Person.is_adult == False).first()
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
