from typing import Optional, List, Dict, Any
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.shared_kernel.enums import MediaType, RoleType, ItemStatus
from app.domains.people.models import Person, MediaPersonLink
from app.domains.metadata.models import MetadataMatch
from app.application.people.schemas import PeopleSearchResponse

class PeopleQueryBuilder:
    def __init__(self, db: Session, library_port: Any, image_service: Any):
        self.db = db
        self.library_port = library_port
        self.image_service = image_service

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
        db = self.db
        statuses = [ItemStatus.MATCHED, ItemStatus.RENAMED, ItemStatus.ORGANIZED]

        matched_match_ids = self.library_port.get_matched_match_ids(statuses)
        
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
                has_identity = bool(person.external_ids) or (len(person.external_links) > 0)
                if not has_identity:
                    continue
            
            if search and search.lower() not in person.name.lower():
                continue
                
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
