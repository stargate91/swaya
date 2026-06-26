from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class PersonRead(BaseSchema):
    id: int
    name: str
    aliases: Optional[List[str]] = None
    birthday: Optional[str] = None
    deathday: Optional[str] = None
    place_of_birth: Optional[str] = None
    gender: Optional[int] = None
    known_for_department: Optional[str] = None
    popularity: Optional[float] = None
    rating_porndb: Optional[float] = None
    scene_count: Optional[int] = None
    profile_path: Optional[str] = None
    local_profile_path: Optional[str] = None
    homepage: Optional[str] = None
    external_ids: Optional[dict[str, Any]] = None
    is_adult: bool
    
    # Extended/Adult Attributes
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    ethnicity: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    measurements: Optional[str] = None
    cup_size: Optional[str] = None
    band_size: Optional[int] = None
    waist: Optional[int] = None
    hip: Optional[int] = None
    tattoos: Optional[str] = None
    piercings: Optional[str] = None
    same_sex_only: Optional[str] = None
    breast_type: Optional[str] = None
    primary_provider: Optional[str] = None
    field_routing: Optional[dict[str, str]] = None

class PeopleGroupItem(BaseModel):
    id: int
    name: str
    year: Optional[int] = None
    poster_path: Optional[str] = None
    rating: float
    popularity: float
    scene_count: Optional[int] = None
    rating_porndb: Optional[float] = None
    type: str
    is_active: bool
    is_favorite: bool
    user_rating: Optional[float] = None
    birthday: str
    gender: Optional[int] = None
    library_count: int
    people_role: str
    is_adult_person: bool
    external_ids: dict[str, Any]

class PersonSearchItem(BaseModel):
    id: int
    name: str
    profile_path: Optional[str] = None
    gender: Optional[int] = None
    scene_count: Optional[int] = None
    rating_porndb: Optional[float] = None
    popularity: float
    is_adult: bool
    is_active: bool
    library_count: int
    known_for: Optional[str] = None
    external_ids: Optional[dict[str, Any]] = None


class PeopleSearchResponse(BaseModel):
    items: List[PersonSearchItem]
    total: int
    has_more: bool
    offset: int
    limit: int

class PersonCreditItem(BaseSchema):
    id: Any
    title: str
    type: str
    tmdb_id: Optional[int] = 0
    year: Optional[int] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    rating: Optional[float] = 0.0
    rating_porndb: Optional[float] = None
    job: Optional[str] = "Actor"
    character: Optional[str] = None
    in_library: bool
    is_known_for: Optional[bool] = None
    known_for_rank: Optional[int] = None

class PersonFilmographyResponse(BaseModel):
    items: List[PersonCreditItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int

class ExternalLinkDetail(BaseModel):
    provider: str
    external_id: str
    profile_url: Optional[str] = None
    source_data: Optional[dict[str, Any]] = None

class PersonDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    name: str
    alternate_names: List[str]
    biography: Optional[str] = None
    birthday: Optional[str] = None
    deathday: Optional[str] = None
    place_of_birth: Optional[str] = None
    gender: Optional[int] = None
    popularity: float
    scene_count: Optional[int] = None
    rating_porndb: Optional[float] = None
    known_for_department: Optional[str] = None
    is_adult: bool
    profile_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    is_active: bool
    homepage: Optional[str] = None
    external_ids: dict[str, Any]
    images: List[str]
    career_start_year: Optional[int] = None
    career_end_year: Optional[int] = None
    known_for: List[PersonCreditItem]
    total_movie_credits: int
    total_tv_credits: int
    total_scene_credits: int
    initial_movie_credits_page: PersonFilmographyResponse
    initial_tv_credits_page: PersonFilmographyResponse
    initial_scene_credits_page: PersonFilmographyResponse
    external_links: Optional[List[ExternalLinkDetail]] = None
    primary_provider: Optional[str] = None
    field_routing: Optional[dict[str, str]] = None



class PersonStatusUpdate(BaseModel):
    is_active: Optional[bool] = None
    user_rating: Optional[float] = None
    is_favorite: Optional[bool] = None
    user_comment: Optional[str] = None


class PersonAddTmdb(BaseModel):
    tmdb_id: Any
    name: Optional[str] = None
    profile_path: Optional[str] = None
    gender: Optional[int] = None
    is_adult: Optional[bool] = None

class PersonLinkPayload(BaseModel):
    source: str
    external_id: str
    overrides: Optional[dict[str, Any]] = None
    profile_url: Optional[str] = None

class PersonUnlinkPayload(BaseModel):
    source: str
    action: str
