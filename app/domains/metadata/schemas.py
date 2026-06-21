from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict

from app.shared_kernel.enums import (
    Provider,
    MediaType,
)


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- MetadataMatch & Localization Schemas ---

class MetadataLocalizationRead(BaseSchema):
    id: int
    match_id: int
    locale: str
    title: str
    tagline: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    local_poster_path: Optional[str] = None
    logo_path: Optional[str] = None
    local_logo_path: Optional[str] = None
    trailer_url: Optional[str] = None
    origin_country: Optional[List[str]] = None
    original_language: Optional[str] = None
    spoken_languages: Optional[List[str]] = None
    genres: Optional[List[str]] = None


class MetadataMatchRead(BaseSchema):
    id: int
    media_item_id: Optional[int] = None
    parent_id: Optional[int] = None
    collection_id: Optional[int] = None
    provider: Provider
    external_id: str
    media_type: MediaType
    season_number: Optional[int] = None
    episode_number: Optional[Any] = None
    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None

    rating_tmdb: Optional[float] = None
    rating_porndb: Optional[float] = None
    rating_imdb: Optional[float] = None
    rating_rotten: Optional[str] = None
    rating_meta: Optional[int] = None
    vote_count_tmdb: Optional[int] = None
    vote_count_imdb: Optional[int] = None
    budget: Optional[int] = None
    revenue: Optional[int] = None
    release_status: Optional[str] = None
    tv_type: Optional[str] = None
    release_date: Optional[datetime] = None
    last_air_date: Optional[datetime] = None
    popularity: Optional[float] = None
    runtime: Optional[int] = None
    imdb_id: Optional[str] = None
    original_title: Optional[str] = None
    backdrop_path: Optional[str] = None
    local_backdrop_path: Optional[str] = None
    still_path: Optional[str] = None
    local_still_path: Optional[str] = None
    suggested_tags: Optional[List[str]] = None
    stills: Optional[List[str]] = None
    local_stills: Optional[List[str]] = None
    fetched_locales: Optional[List[str]] = None
    raw_metadata: Optional[dict[str, Any]] = None
    is_active: bool
    is_adult: bool
    confidence_score: float


class MetadataResolveRequest(BaseSchema):
    item_id: int
    tmdb_id: Optional[int] = None
    external_id: Optional[str] = None
    type: Optional[str] = "movie"
    media_type: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[Any] = None
    provider: Optional[str] = "tmdb"


class BulkResolveRequest(BaseSchema):
    resolutions: List[MetadataResolveRequest]


class GenericSuccessResponse(BaseSchema):
    status: str = "success"
    message: Optional[str] = None


class BulkActionResponse(BaseSchema):
    status: str = "success"
    count: int = 0
