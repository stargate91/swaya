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
        external_id: Optional[str] = None
    ) -> Person:
        """Finds or creates a Person entity and updates their details, supporting cross-provider deduplication."""
        person = None

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

        # 2. Fallback to finding by name
        if not person:
            for obj in self.db.new:
                if isinstance(obj, Person) and obj.name == name:
                    person = obj
                    break
            if not person:
                person = self.db.query(Person).filter(Person.name == name).first()
        
        external_ids = {}
        if tmdb_id:
            external_ids["tmdb"] = tmdb_id
        if provider and external_id:
            external_ids[provider.value] = str(external_id)

        if not person:
            person = Person(
                name=name,
                profile_path=profile_path,
                gender=gender,
                is_adult=is_adult,
                external_ids=external_ids
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
            
            ids = person.external_ids or {}
            if tmdb_id:
                ids["tmdb"] = tmdb_id
            if provider and external_id:
                ids[provider.value] = str(external_id)
            person.external_ids = ids

        # 3. Create or update ExternalSourceLink relationship
        if provider and external_id:
            link = None
            for existing_link in person.external_links:
                if existing_link.provider == provider and existing_link.external_id == str(external_id):
                    link = existing_link
                    break
            if not link:
                for obj in self.db.new:
                    if isinstance(obj, ExternalSourceLink):
                        if (obj.person_id == person.id or obj.person == person) and obj.provider == provider and obj.external_id == str(external_id):
                            link = obj
                            break
            if not link:
                link = self.db.query(ExternalSourceLink).filter(
                    ExternalSourceLink.person_id == person.id,
                    ExternalSourceLink.provider == provider,
                    ExternalSourceLink.external_id == str(external_id)
                ).first()
            if not link:
                link = ExternalSourceLink(
                    person_id=person.id,
                    provider=provider,
                    external_id=str(external_id)
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

        self.db.flush()
        return person
