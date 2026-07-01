from typing import List, Optional

class ListingFilterParams:
    def __init__(
        self,
        tab: str,
        page: int = 1,
        page_size: int = 40,
        sort_by: str = "title_asc",
        search: str = "",
        selected_tags: Optional[List[str]] = None,
        selected_genre: Optional[str] = None,
        selected_decade: Optional[str] = None,
        selected_year: Optional[int] = None,
        filter_favorite: str = "all",
        filter_watched: str = "all",
        filter_ownership: str = "owned",
        filter_status: str = "active",
        filter_gender: str = "all",
        people_role: str = "all",
        include_adult: bool = False,
        selected_performer_id: Optional[int] = None,
        selected_studio_id: Optional[int] = None,
        filter_hair_color: Optional[str] = None,
        filter_ethnicity: Optional[str] = None,
        filter_eye_color: Optional[str] = None,
        filter_tattoos: Optional[str] = None,
        filter_piercings: Optional[str] = None,
        filter_breast_type: Optional[str] = None,
    ):
        self.tab = tab
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.search = search
        self.selected_tags = selected_tags
        self.selected_genre = selected_genre
        self.selected_decade = selected_decade
        self.selected_year = selected_year
        self.filter_favorite = filter_favorite
        self.filter_watched = filter_watched
        self.filter_ownership = filter_ownership
        self.filter_status = filter_status
        self.filter_gender = filter_gender
        self.people_role = people_role
        self.include_adult = include_adult
        self.selected_performer_id = selected_performer_id
        self.selected_studio_id = selected_studio_id
        self.filter_hair_color = filter_hair_color
        self.filter_ethnicity = filter_ethnicity
        self.filter_eye_color = filter_eye_color
        self.filter_tattoos = filter_tattoos
        self.filter_piercings = filter_piercings
        self.filter_breast_type = filter_breast_type
