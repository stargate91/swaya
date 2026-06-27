from pydantic import BaseModel
from typing import List, Optional

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

    model_config = {"extra": "allow"}

class RecommendationsResponse(BaseModel):
    trending: List[RecommendationItem]
    discover_movies: List[RecommendationItem]
    discover_tv: List[RecommendationItem]
    discover_adult: Optional[List[RecommendationItem]] = None
    top_movie_genre: str
    top_tv_genre: str
    watchlist_item_ids: List[int]

class ActionResponse(BaseModel):
    status: str
    message: Optional[str] = None
    id: Optional[int] = None
    deleted_items: Optional[int] = None
    deleted_extras: Optional[int] = None
    ignored_items: Optional[int] = None
    mode: Optional[str] = None
