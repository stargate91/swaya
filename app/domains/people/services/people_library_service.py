import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.domains.people.models import Person, MediaPersonLink
from app.shared_kernel.user_context import get_current_user_id
from app.domains.people.schemas import PeopleGroupItem
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_service_port import ImageServicePort

logger = logging.getLogger(__name__)


class PeopleLibraryService:
    """
    Service for retrieving people (actors, directors, writers) in the context
    of the user's media library. Lives in the people domain since it primarily
    queries and formats Person entities.
    """

    def __init__(self, db_session: Session, library_port: LibraryPort, user_id: Optional[int] = None, image_service: Optional[ImageServicePort] = None):
        self.db = db_session
        if user_id is None:
            user_id = get_current_user_id()
        self.user_id = user_id
        if library_port is None:
            raise ValueError("library_port is required")
        self.library_port = library_port
        if image_service is None:
            from app.domains.media_assets.services.images import image_processing_service
            image_service = image_processing_service
        self.image_service = image_service

    def get_people_group(
        self,
        role: str,
        filter_status: str = "active",
        tab: str = "people",
        include_adult: bool = False,
    ) -> List[PeopleGroupItem]:
        """
        Retrieves list of actors, directors, or creators grouped by role.
        """
        normalized_role = "all"
        role_lower = str(role or "all").strip().lower()
        if role_lower in ("actors", "actor"):
            normalized_role = "actor"
        elif role_lower in ("directors", "director"):
            normalized_role = "director"
        elif role_lower in ("writers", "writer"):
            normalized_role = "writer"

        # Resolve which matches are in the library using the port
        all_valid_match_ids = self.library_port.get_active_match_ids()

        # Fetch link counts
        links = self.db.query(
            MediaPersonLink.person_id,
            MediaPersonLink.match_id
        ).filter(
            MediaPersonLink.match_id.in_(all_valid_match_ids)
        ).all()
        
        person_projects = {}
        for person_id, match_id in links:
            if person_id not in person_projects:
                person_projects[person_id] = set()
            person_projects[person_id].add(match_id)
            
        project_counts = {
            pid: len(matches_set)
            for pid, matches_set in person_projects.items()
        }

        # Fetch people
        query = self.db.query(Person).options(
            selectinload(Person.media_links)
        )

        if filter_status == "active":
            query = query.filter(Person.is_active == True)
        elif filter_status == "inactive":
            query = query.filter(Person.is_active == False)

        query = query.filter(Person.is_adult == include_adult)

        fallback_name = "Unknown Person"
        if normalized_role == "actor":
            query = query.filter(Person.known_for_department == "Acting")
            fallback_name = "Unknown Actor"
        elif normalized_role == "director":
            query = query.filter(Person.known_for_department.in_(["Directing", "Creator"]))
            fallback_name = "Unknown Director"
        elif normalized_role == "writer":
            query = query.filter(Person.known_for_department == "Writing")
            fallback_name = "Unknown Writer"

        people = query.distinct().all()

        people_list = []
        for person in people:
            override_dict = self.library_port.get_person_user_override(self.user_id, person.id)
            
            raw_poster = (override_dict.get("custom_poster") if override_dict else None) or person.local_profile_path or person.profile_path
            poster_path = self.image_service.resolve_image_url(raw_poster, "people")
            
            people_list.append(PeopleGroupItem(
                id=person.id,
                name=person.name or fallback_name,
                year=None,
                poster_path=poster_path,
                rating=(
                    person.rating_porndb
                    if person.is_adult and person.rating_porndb is not None
                    else person.popularity or 0.0
                ),
                popularity=person.popularity or 0.0,
                scene_count=person.scene_count,
                rating_porndb=person.rating_porndb,
                type="person",
                is_active=person.is_active,
                is_favorite=override_dict.get("is_favorite") if override_dict else False,
                user_rating=override_dict.get("user_rating") if override_dict else None,
                user_comment=override_dict.get("user_comment") if override_dict else None,
                birthday=person.birthday or "",
                gender=person.gender,
                library_count=project_counts.get(person.id, 0),
                people_role=person.known_for_department.lower() if person.known_for_department else "person",
                is_adult_person=person.is_adult,
                external_ids=person.external_ids or {},
                cup_size=person.cup_size,
                band_size=person.band_size,
                waist=person.waist,
                hip=person.hip,
                hair_color=person.hair_color,
                ethnicity=person.ethnicity,
                eye_color=person.eye_color,
                tattoos=person.tattoos,
                piercings=person.piercings,
                breast_type=person.breast_type,
            ))

        return people_list
