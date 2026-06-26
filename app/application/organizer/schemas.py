from pydantic import BaseModel, Field
from typing import List, Optional, Any

class OrganizerItemImage(BaseModel):
    path: str

class OrganizerMatch(BaseModel):
    id: int
    tmdb_id: Optional[Any] = None
    type: str
    title: str
    year: Optional[int] = None
    poster_path: Optional[str] = None
    vote_average: Optional[float] = None
    is_active: bool
    confidence: Optional[float] = None
    is_adult: Optional[bool] = None
    provider: Optional[str] = None

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
    season: Optional[str] = None
    episode: Optional[str] = None
    custom_edition: Optional[str] = None
    custom_audio_type: Optional[str] = None
    custom_source: Optional[str] = None
    parsed_info: Optional[dict] = None

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
    parent_is_adult: Optional[bool] = None

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
