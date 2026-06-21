from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
from app.shared_kernel.enums import MovieEdition, MediaAudioType, MediaSource, CustomListType

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- User Schemas ---

class UserCreate(BaseSchema):
    username: str
    email: Optional[str] = None
    password_hash: Optional[str] = None
    pin_hash: Optional[str] = None
    role: Optional[str] = None
    managed_by_user_id: Optional[int] = None
    allow_adult: bool = False


class UserRead(BaseSchema):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    managed_by_user_id: Optional[int] = None
    is_active: bool
    allow_adult: bool
    created_at: datetime


# --- UserOverride Schemas ---

class UserOverrideCreate(BaseSchema):
    user_id: int
    media_item_id: Optional[int] = None
    metadata_match_id: Optional[int] = None
    person_id: Optional[int] = None
    studio_id: Optional[int] = None
    collection_id: Optional[int] = None
    custom_title: Optional[str] = None
    custom_overview: Optional[str] = None
    custom_poster: Optional[str] = None
    custom_backdrop: Optional[str] = None
    custom_logo: Optional[str] = None
    custom_language: Optional[str] = None
    custom_edition: Optional[MovieEdition] = None
    custom_audio_type: Optional[MediaAudioType] = None
    custom_source: Optional[MediaSource] = None
    user_rating: Optional[int] = None
    user_comment: Optional[str] = None
    is_favorite: bool = False
    is_watched: bool = False
    is_tracked: bool = False


class UserOverrideRead(BaseSchema):
    id: int
    user_id: int
    media_item_id: Optional[int] = None
    metadata_match_id: Optional[int] = None
    person_id: Optional[int] = None
    studio_id: Optional[int] = None
    collection_id: Optional[int] = None
    custom_title: Optional[str] = None
    custom_overview: Optional[str] = None
    custom_poster: Optional[str] = None
    custom_backdrop: Optional[str] = None
    custom_logo: Optional[str] = None
    custom_language: Optional[str] = None
    custom_edition: Optional[MovieEdition] = None
    custom_audio_type: Optional[MediaAudioType] = None
    custom_source: Optional[MediaSource] = None
    user_rating: Optional[int] = None
    user_rating_at: Optional[datetime] = None
    user_comment: Optional[str] = None
    user_comment_at: Optional[datetime] = None
    is_favorite: bool
    is_favorite_at: Optional[datetime] = None
    is_watched: bool
    last_watched_at: Optional[datetime] = None
    watch_count: int
    resume_position: int
    is_tracked: bool


# --- CustomList Schemas ---

class CustomListCreate(BaseSchema):
    user_id: int
    name: str
    description: Optional[str] = None
    list_type: CustomListType = CustomListType.MEDIA
    color: Optional[str] = None
    icon: Optional[str] = None


class CustomListItemRead(BaseSchema):
    id: int
    list_id: int
    media_item_id: Optional[int] = None
    match_id: Optional[int] = None
    person_id: Optional[int] = None
    studio_id: Optional[int] = None
    collection_id: Optional[int] = None
    added_at: datetime
    order: int


class CustomListRead(BaseSchema):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    list_type: CustomListType
    color: Optional[str] = None
    icon: Optional[str] = None
    created_at: datetime


# --- UserOverride Action Schemas (Legacy Endpoints) ---

class ItemOverridesUpdate(BaseSchema):
    item_id: str
    custom_title: Optional[str] = None
    custom_overview: Optional[str] = None
    custom_language: Optional[str] = None
    user_rating: Optional[int] = None
    rating: Optional[int] = None
    user_comment: Optional[str] = None
    comment: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_watched: Optional[bool] = None
    resume_position: Optional[int] = None
    tags: Optional[List[Any]] = None


class ItemStatusUpdate(BaseSchema):
    status: str


class ImageOverrideUpdate(BaseSchema):
    path: Optional[str] = None
    url: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    logo_path: Optional[str] = None


class BulkOverridesUpdate(BaseSchema):
    item_ids: List[str]
    updates: dict[str, Any]


class BulkTagsUpdate(BaseSchema):
    item_ids: List[str]
    tag_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    action: str = "add"


class BulkWatchedUpdate(BaseSchema):
    item_ids: List[str]
    is_watched: bool = True
    watched_at: Optional[str] = None
    last_watched_at: Optional[str] = None
