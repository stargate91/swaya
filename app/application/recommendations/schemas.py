from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class RecommendationItem(BaseModel):
    id: int
    title: Optional[str] = None
    name: Optional[str] = None
    original_title: Optional[str] = None
    original_name: Optional[str] = None
    media_type: str
    in_library: bool
    media_item_id: Optional[int] = None
    rating_imdb: Optional[float] = None
    rating_tmdb: Optional[float] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    release_date: Optional[str] = None
    first_air_date: Optional[str] = None
    overview: Optional[str] = None

    model_config = {"extra": "allow"}  # Allows extra attributes from TMDB scraper to pass through

class RecommendationsResponse(BaseModel):
    trending: List[RecommendationItem]
    discover_movies: List[RecommendationItem]
    discover_tv: List[RecommendationItem]
    top_movie_genre: str
    top_tv_genre: str
    watchlist_item_ids: List[int]

class OrganizerItemImage(BaseModel):
    path: str

class OrganizerMatch(BaseModel):
    id: int
    tmdb_id: Optional[int] = None
    type: str
    title: str
    year: Optional[int] = None
    poster_path: Optional[str] = None
    vote_average: Optional[float] = None
    is_active: bool
    confidence: Optional[float] = None
    is_adult: Optional[bool] = None

class OrganizerItem(BaseModel):
    id: int
    filename: str
    status: str
    type: str
    title: str
    planned_path: Optional[str] = None
    extension: str
    size_mb: float
    images: List[OrganizerItemImage]
    matches: List[OrganizerMatch]
    current_path: Optional[str] = None
    action: Optional[str] = None
    target_language: Optional[str] = None
    scan_mode: Optional[str] = None

class OrganizerExtra(BaseModel):
    id: int
    parent_id: int
    parent_type: str
    parent_status: Optional[str] = None
    parent_name: str
    filename: str
    extension: str
    category: str
    subtype: str
    language: Optional[str] = None
    path: str
    planned_path: str
    action: str
    parent_scan_mode: Optional[str] = None

class OrganizerGroupsResponse(BaseModel):
    manual: List[OrganizerItem]
    movies: List[OrganizerItem]
    tv: List[OrganizerItem]
    extras: List[OrganizerExtra]
    collisions: List[Any] = Field(default_factory=list)

class ActionResponse(BaseModel):
    status: str
    message: Optional[str] = None
    id: Optional[int] = None
    deleted_items: Optional[int] = None
    deleted_extras: Optional[int] = None
    ignored_items: Optional[int] = None
    mode: Optional[str] = None
