from typing import Tuple, List
from sqlalchemy.orm import Session

from app.domains.people.services.people_library_service import PeopleLibraryService
from app.domains.library.services.listing.filter_params import ListingFilterParams

class PeopleQueryBuilder:
    def __init__(self, db: Session):
        self.db = db

    def query_people(self, params: ListingFilterParams) -> Tuple[int, List[dict]]:
        people_service = PeopleLibraryService(self.db)
        people_items = people_service.get_people_group(
            role=params.people_role,
            filter_status=params.filter_status,
            tab=params.tab,
            include_adult=params.include_adult,
        )

        if params.search:
            search_lower = params.search.lower()
            people_items = [
                item for item in people_items
                if search_lower in (item.name or "").lower()
            ]

        if params.filter_gender == "female":
            people_items = [item for item in people_items if item.gender == 1]
        elif params.filter_gender == "male":
            people_items = [item for item in people_items if item.gender == 2]

        if params.filter_favorite == "favorite":
            people_items = [item for item in people_items if item.is_favorite]
        elif params.filter_favorite == "not_favorite":
            people_items = [item for item in people_items if not item.is_favorite]

        if params.sort_by in ("library_count", "library_count_desc"):
            people_items.sort(key=lambda item: (-(item.library_count or 0), -(item.rating or 0.0), (item.name or "").lower()))
        elif params.sort_by == "library_count_asc":
            people_items.sort(key=lambda item: ((item.library_count or 0), (item.rating or 0.0), (item.name or "").lower()))
        elif params.sort_by in ("rating_desc", "user_rating_desc", "popularity_desc"):
            people_items.sort(key=lambda item: (-(item.user_rating if item.user_rating is not None else item.rating or 0.0), -(item.library_count or 0), (item.name or "").lower()))
        elif params.sort_by in ("user_rating_asc", "popularity_asc"):
            people_items.sort(key=lambda item: ((item.user_rating if item.user_rating is not None else item.rating or 0.0), (item.library_count or 0), (item.name or "").lower()))
        elif params.sort_by in ("name_desc", "title_desc"):
            people_items.sort(key=lambda item: (item.name or "").lower(), reverse=True)
        else:
            people_items.sort(key=lambda item: (item.name or "").lower())

        total_items = len(people_items)
        paged_people = people_items[(params.page - 1) * params.page_size: params.page * params.page_size]

        formatted_items = [
            {
                "id": item.id,
                "title": item.name,
                "name": item.name,
                "year": item.year,
                "poster_path": item.poster_path,
                "backdrop_path": None,
                "rating": item.rating,
                "rating_porndb": item.rating_porndb,
                "rating_imdb": None,
                "type": item.type,
                "path": None,
                "duration": 0.0,
                "size": 0,
                "in_library": True,
                "release_date": None,
                "user_rating": item.user_rating,
                "is_favorite": item.is_favorite,
                "is_active": item.is_active,
                "gender": item.gender,
                "library_count": item.library_count,
                "people_role": item.people_role,
                "is_adult_person": item.is_adult_person,
                "external_ids": item.external_ids,
            }
            for item in paged_people
        ]

        return total_items, formatted_items
