from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional, List, Any, Union
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
    user_rating: Optional[float] = None
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
    user_rating: Optional[float] = None
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

def _unpack_nested_updates(data):
    """Merge nested 'updates' dict into top-level fields."""
    if not isinstance(data, dict):
        return data
    nested = data.get("updates")
    if not isinstance(nested, dict):
        return data
    for key, value in nested.items():
        if data.get(key) is None:
            data[key] = value
    return data

class ItemOverridesUpdate(BaseSchema):
    item_id: Optional[Union[str, int]] = None
    id: Optional[Union[str, int]] = None
    type: Optional[str] = None
    updates: Optional[dict[str, Any]] = None
    custom_title: Optional[str] = None
    custom_overview: Optional[str] = None
    custom_language: Optional[str] = None
    custom_edition: Optional[str] = None
    custom_audio_type: Optional[str] = None
    custom_source: Optional[str] = None
    season: Optional[str] = None
    episode: Optional[str] = None
    main_type: Optional[str] = None
    parent_id: Optional[int] = None
    reset_match: Optional[bool] = None
    subtype: Optional[str] = None
    language: Optional[str] = None
    user_rating: Optional[float] = None
    user_comment: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_watched: Optional[bool] = None
    resume_position: Optional[int] = None
    tags: Optional[List[Any]] = None
    media_type: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _unpack_updates(cls, data):
        return _unpack_nested_updates(data)

    @model_validator(mode="after")
    def _normalize_ids(self):
        if self.item_id is None and self.id is not None:
            self.item_id = str(self.id)
        elif self.item_id is not None:
            self.item_id = str(self.item_id)
        return self


class ItemStatusUpdate(BaseSchema):
    status: Optional[str] = None
    user_rating: Optional[float] = None
    user_comment: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_watched: Optional[bool] = None
    media_type: Optional[str] = None
    custom_tags: Optional[List[Any]] = None
    tags: Optional[List[Any]] = None
    resume_position: Optional[int] = None


class ImageOverrideUpdate(BaseSchema):
    path: Optional[str] = None
    url: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    logo_path: Optional[str] = None
    profile_path: Optional[str] = None
    media_type: Optional[str] = None


class BulkOverridesUpdate(BaseSchema):
    item_ids: List[Union[str, int]] = []
    ids: Optional[List[Union[str, int]]] = None
    type: Optional[str] = None
    updates: Optional[dict[str, Any]] = None
    custom_edition: Optional[str] = None
    custom_audio_type: Optional[str] = None
    custom_source: Optional[str] = None
    custom_language: Optional[str] = None
    season: Optional[str] = None
    episode: Optional[str] = None
    main_type: Optional[str] = None
    parent_id: Optional[int] = None
    reset_match: Optional[bool] = None
    subtype: Optional[str] = None
    language: Optional[str] = None
    item_updates: Optional[List[dict[str, Any]]] = None

    @model_validator(mode="before")
    @classmethod
    def _unpack_updates(cls, data):
        return _unpack_nested_updates(data)

    @model_validator(mode="after")
    def _normalize_ids(self):
        if (not self.item_ids) and self.ids:
            self.item_ids = [str(item_id) for item_id in self.ids]
        else:
            self.item_ids = [str(item_id) for item_id in self.item_ids]
        return self


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


class CustomTagImage(BaseModel):
    path: str
    position_x: int
    position_y: int


class TagResponse(BaseModel):
    id: int
    name: str
    color: str
    target_type: str
    is_adult: bool
    custom_images: List[CustomTagImage]


class CustomListItemResponse(BaseModel):
    id: int
    media_item_id: Optional[int] = None
    match_id: Optional[int] = None
    person_id: Optional[int] = None
    studio_id: Optional[int] = None
    collection_id: Optional[int] = None
    added_at: Optional[str] = None
    title: Optional[str] = None
    tmdb_id: Optional[int] = None
    media_type: Optional[str] = None
    poster_path: Optional[str] = None


class CustomListResponse(BaseModel):
    id: int
    name: str
    is_watchlist: bool
    description: Optional[str] = None
    color: str
    icon: str
    created_at: Optional[str] = None
    item_count: int
    sample_posters: List[str]


class CustomListDetailResponse(BaseModel):
    id: int
    name: str
    is_watchlist: bool
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    created_at: Optional[str] = None
    items: List[CustomListItemResponse]


class ListMembershipResponse(BaseModel):
    list_ids: List[int]


class CatalogItemResponse(BaseModel):
    id: int
    title: str
    media_type: str
    poster_path: Optional[str] = None
    user_rating: Optional[float] = 0
    is_favorite: bool = False


class CatalogPageResponse(BaseModel):
    tab: Optional[str] = None
    offset: int
    limit: int
    returned: int
    has_more: bool


class CatalogResponse(BaseModel):
    movies: List[CatalogItemResponse]
    tv: List[CatalogItemResponse]
    people: List[CatalogItemResponse]
    counts: dict[str, int]
    page: CatalogPageResponse


class BulkUpdateResponse(BaseModel):
    status: str
    tab: str
    updated_ids: List[Any]


