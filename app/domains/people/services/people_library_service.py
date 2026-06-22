import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import Person, MediaPersonLink
from app.domains.users.models import UserOverride
from app.shared_kernel.enums import ItemStatus

logger = logging.getLogger(__name__)


class PeopleLibraryService:
    """
    Service for retrieving people (actors, directors, writers) in the context
    of the user's media library. Lives in the people domain since it primarily
    queries and formats Person entities.
    """

    def __init__(self, db_session: Session, user_id: int = 1):
        self.db = db_session
        self.user_id = user_id

    def get_people_group(
        self,
        role: str,
        filter_status: str = "active",
        tab: str = "people",
        include_adult: bool = False,
    ) -> list[dict[str, Any]]:
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

        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]
        
        # 1. Resolve which matches are in the library
        library_match_ids = {
            r[0] for r in self.db.query(MetadataMatch.id).join(
                MediaItem, MetadataMatch.media_item_id == MediaItem.id
            ).filter(MediaItem.status.in_(lib_statuses)).all()
        }
        
        # 2. Get parent IDs for TV show / season hierarchies
        parent_ids = set()
        current_parents = {
            r[0] for r in self.db.query(MetadataMatch.parent_id).join(
                MediaItem, MetadataMatch.media_item_id == MediaItem.id
            ).filter(MediaItem.status.in_(lib_statuses), MetadataMatch.parent_id != None).all()
        }
        while current_parents:
            parent_ids.update(current_parents)
            current_parents = {
                r[0] for r in self.db.query(MetadataMatch.parent_id).filter(
                    MetadataMatch.id.in_(current_parents), MetadataMatch.parent_id != None
                ).all()
            }
            
        all_valid_match_ids = library_match_ids.union(parent_ids)

        # 3. Fetch link counts
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

        # 4. Fetch people
        query = self.db.query(Person).options(
            selectinload(Person.media_links),
            selectinload(Person.overrides)
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
            o = next((ov for ov in person.overrides if ov.user_id == self.user_id), None) if person.overrides else None
            
            poster_path = (o.custom_poster if (o and o.custom_poster) else None) or person.local_profile_path or person.profile_path
            
            people_list.append({
                "id": person.id,
                "name": person.name or fallback_name,
                "year": None,
                "poster_path": poster_path,
                "rating": (
                    person.rating_porndb
                    if person.is_adult and person.rating_porndb is not None
                    else person.popularity or 0.0
                ),
                "popularity": person.popularity or 0.0,
                "scene_count": person.scene_count,
                "rating_porndb": person.rating_porndb,
                "type": "person",
                "is_active": person.is_active,
                "is_favorite": o.is_favorite if o else False,
                "user_rating": o.user_rating if o else None,
                "birthday": person.birthday or "",
                "gender": person.gender,
                "library_count": project_counts.get(person.id, 0),
                "people_role": person.known_for_department.lower() if person.known_for_department else "person",
                "is_adult_person": person.is_adult,
                "external_ids": person.external_ids or {},
            })

        return people_list
