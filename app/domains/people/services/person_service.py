import logging
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from app.domains.people.models import Person, ExternalSourceLink
from app.shared_kernel.enums import Provider
from app.domains.people.helpers import (
    known_for_score,
    select_known_for,
    resolve_person_known_for_backdrop,
)

logger = logging.getLogger(__name__)

class PersonService:
    """
    Public service interface for Person entities.
    Encapsulates creating and updating cast members and performers to maintain cross-domain integrity.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def update_or_create_person(
        self,
        name: str,
        profile_path: str = None,
        gender: int = None,
        is_adult: bool = False,
        tmdb_id: str = None,
        performer_details: dict = None,
        provider: Optional[Provider] = None,
        external_id: Optional[str] = None,
        known_for_department: Optional[str] = None,
        urls: Optional[List[str]] = None
    ) -> Person:
        """Finds or creates a Person entity and updates their details, supporting cross-provider deduplication."""
        person = None
        extracted_ids = {}

        # Extract external IDs from urls unconditionally
        if urls:
            import re
            for u in urls:
                url_str = u.get("url") if isinstance(u, dict) else u
                if not url_str or not isinstance(url_str, str):
                    continue
                match_stash = re.search(r'stashdb\.org/performers/([a-fA-F0-9\-]+)', url_str)
                if match_stash:
                    extracted_ids[Provider.STASHDB] = match_stash.group(1)
                match_fans = re.search(r'fansdb\.cc/performers/([a-fA-F0-9\-]+)', url_str)
                if match_fans:
                    extracted_ids[Provider.FANSDB] = match_fans.group(1)
                match_porn = re.search(r'theporndb\.net/performers/([a-fA-F0-9\-]+)', url_str)
                if match_porn:
                    extracted_ids[Provider.PORNDB] = match_porn.group(1)
                match_tmdb = re.search(r'themoviedb\.org/person/(\d+)', url_str)
                if match_tmdb:
                    extracted_ids["tmdb"] = match_tmdb.group(1)

        # 1. Try finding by provider and external_id
        if provider and external_id:
            for obj in self.db.new:
                if isinstance(obj, ExternalSourceLink):
                    if obj.provider == provider and obj.external_id == str(external_id):
                        person = obj.person
                        break
            if not person:
                link = self.db.query(ExternalSourceLink).filter(
                    ExternalSourceLink.provider == provider,
                    ExternalSourceLink.external_id == str(external_id)
                ).first()
                if link:
                    person = link.person

        # 1.5 Try finding by tmdb_id
        if not person and tmdb_id:
            for obj in self.db.new:
                if isinstance(obj, Person) and obj.external_ids and obj.external_ids.get("tmdb") == str(tmdb_id):
                    person = obj
                    break
            if not person:
                person = self.db.query(Person).filter(Person.external_ids["tmdb"] == str(tmdb_id)).first()

        # 1.6 Try finding by extracted IDs from URLs
        if not person and extracted_ids:
            for ext_prov in ["tmdb", Provider.STASHDB, Provider.FANSDB, Provider.PORNDB]:
                if ext_prov not in extracted_ids:
                    continue
                ext_val = extracted_ids[ext_prov]
                if ext_prov == "tmdb":
                    for obj in self.db.new:
                        if isinstance(obj, Person) and obj.external_ids and obj.external_ids.get("tmdb") == str(ext_val):
                            person = obj
                            break
                    if not person:
                        person = self.db.query(Person).filter(Person.external_ids["tmdb"] == str(ext_val)).first()
                else:
                    for obj in self.db.new:
                        if isinstance(obj, ExternalSourceLink):
                            if obj.provider == ext_prov and obj.external_id == str(ext_val):
                                person = obj.person
                                break
                    if not person:
                        link = self.db.query(ExternalSourceLink).filter(
                            ExternalSourceLink.provider == ext_prov,
                            ExternalSourceLink.external_id == str(ext_val)
                        ).first()
                        if link:
                            person = link.person
                if person:
                    break

        if not person:
            person = Person(
                name=name,
                profile_path=profile_path,
                gender=gender,
                is_adult=is_adult,
                known_for_department=known_for_department or ("Acting" if is_adult else None),
                external_ids={}
            )
            self.db.add(person)
            self.db.flush()
        else:
            if profile_path:
                person.profile_path = profile_path
            if gender is not None:
                person.gender = gender
            if is_adult:
                person.is_adult = is_adult
            
            if known_for_department:
                person.known_for_department = known_for_department
            elif is_adult and not person.known_for_department:
                person.known_for_department = "Acting"

        # Update external_ids dictionary
        all_links = dict(extracted_ids)
        if provider and external_id:
            all_links[provider] = str(external_id)
        if tmdb_id:
            all_links[Provider.TMDB] = str(tmdb_id)

        ids = person.external_ids or {}
        for ext_prov, ext_val in all_links.items():
            key = ext_prov.value if isinstance(ext_prov, Provider) else str(ext_prov)
            ids[key] = str(ext_val)
            ids[f"{key}_id"] = str(ext_val)
        
        if urls:
            existing_urls = ids.get("urls") or []
            existing_urls_set = {u.get("url") if isinstance(u, dict) else u for u in existing_urls}
            for new_url in urls:
                url_str = new_url.get("url") if isinstance(new_url, dict) else new_url
                if url_str and url_str not in existing_urls_set:
                    existing_urls.append({"url": url_str})
                    existing_urls_set.add(url_str)
            ids["urls"] = existing_urls
        person.external_ids = ids

        # 3. Create or update ExternalSourceLink relationships for all resolved links
        for ext_prov, ext_val in all_links.items():
            prov_enum = ext_prov
            if isinstance(prov_enum, str):
                try:
                    prov_enum = Provider(prov_enum)
                except ValueError:
                    continue

            link = None
            for existing_link in person.external_links:
                if existing_link.provider == prov_enum and existing_link.external_id == str(ext_val):
                    link = existing_link
                    break
            if not link:
                for obj in self.db.new:
                    if isinstance(obj, ExternalSourceLink):
                        if (obj.person_id == person.id or obj.person == person) and obj.provider == prov_enum and obj.external_id == str(ext_val):
                            link = obj
                            break
            if not link:
                link = self.db.query(ExternalSourceLink).filter(
                    ExternalSourceLink.person_id == person.id,
                    ExternalSourceLink.provider == prov_enum,
                    ExternalSourceLink.external_id == str(ext_val)
                ).first()
            if not link:
                link = ExternalSourceLink(
                    person_id=person.id,
                    provider=prov_enum,
                    external_id=str(ext_val)
                )
                self.db.add(link)

        # Map adult performer details if provided
        if performer_details:
            for key, val in performer_details.items():
                if not hasattr(person, key) or val is None:
                    continue
                if key == "scene_count":
                    person.scene_count = max(person.scene_count or 0, int(val))
                else:
                    setattr(person, key, val)
            if not person.known_for_department:
                person.known_for_department = "Acting"

        self.db.flush()
        return person
