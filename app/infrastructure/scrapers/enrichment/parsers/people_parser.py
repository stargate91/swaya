from typing import Dict, Any
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.enums import MediaType, RoleType
from app.domains.people.services import PersonService

def process_people(parser, match: MetadataMatch, details: Dict[str, Any]):
    credits = details.get("aggregate_credits", {}) if match.media_type != MediaType.MOVIE else details.get("credits", {})
    if not credits or not credits.get("cast"):
        credits = details.get("credits", {})
        
    cast = credits.get("cast", [])[:15]
    crew = credits.get("crew", [])
    
    person_service = PersonService(parser.db)
    
    # Link Actors
    for idx, cast_member in enumerate(cast):
        person = person_service.update_or_create_person(
            name=cast_member["name"],
            profile_path=cast_member.get("profile_path"),
            gender=cast_member.get("gender"),
            is_adult=cast_member.get("adult", False),
            tmdb_id=str(cast_member["id"]),
            known_for_department=cast_member.get("known_for_department")
        )
        
        link = parser.people_repo.get_media_person_link(match.id, person.id, RoleType.ACTOR)
        
        if not link:
            link = parser.people_repo.create_media_person_link(
                role=RoleType.ACTOR,
                character_name=cast_member.get("character") or (cast_member.get("roles", [{}])[0].get("character") if "roles" in cast_member else None),
                order=idx,
                match_id=match.id,
                person_id=person.id
            )

    # Link Directors
    directors = [p for p in crew if p.get("job") == "Director"][:2]
    for idx, dir_member in enumerate(directors):
        person = person_service.update_or_create_person(
            name=dir_member["name"],
            profile_path=dir_member.get("profile_path"),
            gender=dir_member.get("gender"),
            is_adult=dir_member.get("adult", False),
            tmdb_id=str(dir_member["id"]),
            known_for_department=dir_member.get("known_for_department")
        )
        
        link = parser.people_repo.get_media_person_link(match.id, person.id, RoleType.DIRECTOR)
        
        if not link:
            link = parser.people_repo.create_media_person_link(
                role=RoleType.DIRECTOR,
                order=idx,
                match_id=match.id,
                person_id=person.id
            )
