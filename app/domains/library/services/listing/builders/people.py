from typing import Tuple, List
from sqlalchemy.orm import Session

from app.domains.people.services.people_library_service import PeopleLibraryService
from app.domains.library.services.listing.filter_params import ListingFilterParams

from app.shared_kernel.ports.library_port import LibraryPort

class PeopleQueryBuilder:
    def __init__(self, db: Session, library_port: LibraryPort):
        self.db = db
        self.library_port = library_port

    def query_people(self, params: ListingFilterParams) -> Tuple[int, List[dict]]:
        people_service = PeopleLibraryService(self.db, library_port=self.library_port)
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

        if params.filter_hair_color:
            people_items = [item for item in people_items if item.hair_color == params.filter_hair_color]
        if params.filter_ethnicity:
            people_items = [item for item in people_items if item.ethnicity == params.filter_ethnicity]
        if params.filter_eye_color:
            people_items = [item for item in people_items if item.eye_color == params.filter_eye_color]
        if params.filter_tattoos:
            if params.filter_tattoos.lower() == "yes":
                people_items = [item for item in people_items if item.tattoos and str(item.tattoos).strip().lower() not in ("no", "none", "nincs")]
            else:
                people_items = [item for item in people_items if not item.tattoos or str(item.tattoos).strip().lower() in ("no", "none", "nincs")]
        if params.filter_piercings:
            if params.filter_piercings.lower() == "yes":
                people_items = [item for item in people_items if item.piercings and str(item.piercings).strip().lower() not in ("no", "none", "nincs")]
            else:
                people_items = [item for item in people_items if not item.piercings or str(item.piercings).strip().lower() in ("no", "none", "nincs")]
        if params.filter_breast_type:
            people_items = [item for item in people_items if item.breast_type == params.filter_breast_type]

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
        elif params.sort_by in ("birthday", "birthday_desc"):
            people_items.sort(key=lambda item: (item.birthday or "0000-00-00", (item.name or "").lower()), reverse=True)
        elif params.sort_by == "birthday_asc":
            people_items.sort(key=lambda item: (item.birthday or "9999-99-99", (item.name or "").lower()))
        elif params.sort_by in ("cup_size_desc", "cup_size_asc"):
            cup_order = {
                'A': 1, 'B': 2, 'C': 3, 'D': 4, 'DD': 5, 'DDD': 6, 'E': 7, 'EE': 8, 'F': 9, 'FF': 10,
                'G': 11, 'GG': 12, 'H': 13, 'HH': 14, 'I': 15, 'J': 16, 'K': 17
            }
            if params.sort_by == "cup_size_desc":
                people_items.sort(key=lambda item: (
                    -cup_order.get(str(item.cup_size or "").strip().upper(), 0),
                    -(item.band_size or 0),
                    (item.name or "").lower()
                ))
            else:
                people_items.sort(key=lambda item: (
                    cup_order.get(str(item.cup_size or "").strip().upper(), 99),
                    item.band_size or 999,
                    (item.name or "").lower()
                ))
        elif params.sort_by == "waist_desc":
            people_items.sort(key=lambda item: (
                -(item.waist or 0),
                (item.name or "").lower()
            ))
        elif params.sort_by == "waist_asc":
            people_items.sort(key=lambda item: (
                item.waist or 999,
                (item.name or "").lower()
            ))
        elif params.sort_by == "hip_desc":
            people_items.sort(key=lambda item: (
                -(item.hip or 0),
                (item.name or "").lower()
            ))
        elif params.sort_by == "hip_asc":
            people_items.sort(key=lambda item: (
                item.hip or 999,
                (item.name or "").lower()
            ))
        elif params.sort_by in ("hourglass_ratio_desc", "hourglass_ratio_asc"):
            def get_whr(item):
                try:
                    w = float(item.waist) if item.waist else 0.0
                    h = float(item.hip) if item.hip else 0.0
                    if w > 0 and h > 0:
                        return w / h
                except (ValueError, TypeError):
                    pass
                return None

            if params.sort_by == "hourglass_ratio_asc":
                people_items.sort(key=lambda item: (
                    get_whr(item) if get_whr(item) is not None else 9.9,
                    (item.name or "").lower()
                ))
            else:
                people_items.sort(key=lambda item: (
                    -get_whr(item) if get_whr(item) is not None else 9.9,
                    (item.name or "").lower()
                ))
        elif params.sort_by in ("body_slender_asc", "body_slender_desc"):
            def get_slender_score(item):
                try:
                    w = float(item.waist) if item.waist else 0.0
                    h = float(item.hip) if item.hip else 0.0
                    if w > 0 and h > 0:
                        return w + h
                except (ValueError, TypeError):
                    pass
                return None

            if params.sort_by == "body_slender_asc":
                people_items.sort(key=lambda item: (
                    get_slender_score(item) if get_slender_score(item) is not None else 999.0,
                    (item.name or "").lower()
                ))
            else:
                people_items.sort(key=lambda item: (
                    -get_slender_score(item) if get_slender_score(item) is not None else 999.0,
                    (item.name or "").lower()
                ))
        elif params.sort_by in ("body_curvy_desc", "body_curvy_asc"):
            def get_curvy_score(item):
                try:
                    w = float(item.waist) if item.waist else 0.0
                    h = float(item.hip) if item.hip else 0.0
                    if w > 0 and h > 0:
                        return h - w
                except (ValueError, TypeError):
                    pass
                return None

            if params.sort_by == "body_curvy_desc":
                people_items.sort(key=lambda item: (
                    -get_curvy_score(item) if get_curvy_score(item) is not None else -999.0,
                    (item.name or "").lower()
                ))
            else:
                people_items.sort(key=lambda item: (
                    get_curvy_score(item) if get_curvy_score(item) is not None else 999.0,
                    (item.name or "").lower()
                ))
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
                "user_comment": item.user_comment,
                "is_favorite": item.is_favorite,
                "is_active": item.is_active,
                "gender": item.gender,
                "birthday": item.birthday,
                "library_count": item.library_count,
                "people_role": item.people_role,
                "is_adult_person": item.is_adult_person,
                "external_ids": item.external_ids,
                "cup_size": item.cup_size,
                "band_size": item.band_size,
                "waist": item.waist,
                "hip": item.hip,
                "hair_color": item.hair_color,
                "ethnicity": item.ethnicity,
                "eye_color": item.eye_color,
                "tattoos": item.tattoos,
                "piercings": item.piercings,
                "breast_type": item.breast_type,
            }
            for item in paged_people
        ]

        return total_items, formatted_items
