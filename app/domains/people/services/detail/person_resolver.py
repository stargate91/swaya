import logging
from typing import Any
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.shared_kernel.enums import Provider
from app.domains.people.models import Person, ExternalSourceLink

logger = logging.getLogger(__name__)

class PersonResolver:
    def __init__(self, db: Session, search_service: Any):
        self.db = db
        self.search_service = search_service

    def resolve_person(self, person_id: Any, load_localizations: bool = False) -> Person:
        db = self.db
        query = db.query(Person)
        if load_localizations:
            query = query.options(joinedload(Person.localizations), joinedload(Person.external_links))
        
        person = None
        person_id_str = str(person_id)
        if person_id_str.startswith("local:"):
            try:
                p_id = int(person_id_str.split(":", 1)[1])
                person = query.filter(Person.id == p_id).first()
            except (ValueError, TypeError) as e:
                logger.debug(f"Swallowed exception: {e}", exc_info=True)
        elif person_id_str.startswith("tmdb:"):
            try:
                tmdb_id_val = person_id_str.split(":", 1)[1]
                person = query.filter(
                    Person.external_ids["tmdb"].as_string() == tmdb_id_val
                ).first()
                if not person:
                    res = self.search_service.add_person_tmdb(tmdb_id_val)
                    if res and res.get("status") == "success":
                        query_new = db.query(Person)
                        if load_localizations:
                            query_new = query_new.options(joinedload(Person.localizations), joinedload(Person.external_links))
                        person = query_new.filter(Person.id == res["id"]).first()
            except Exception as e:
                logger.error(f"Error dynamically importing person via tmdb prefix {person_id_str}: {e}")
        elif ":" not in person_id_str:
            try:
                p_id = int(person_id_str)
                person = query.filter(Person.id == p_id).first()
            except (ValueError, TypeError) as e:
                logger.debug(f"Swallowed exception: {e}", exc_info=True)
        
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
                except Exception as e:
                    logger.debug(f"Swallowed exception: {e}", exc_info=True)
            else:
                query_ext = db.query(Person)
                if load_localizations:
                    query_ext = query_ext.options(joinedload(Person.localizations))
                person = query_ext.filter(
                    Person.external_ids["tmdb"].as_string() == person_id_str
                ).first()
            
            if not person:
                try:
                    res = self.search_service.add_person_tmdb(str(person_id))
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
