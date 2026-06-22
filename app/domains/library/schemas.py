from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict

from app.shared_kernel.enums import (
    ItemStatus,
    MovieEdition,
    MediaSource,
    MediaAudioType,
    ExtraCategory,
    ExtraSubtype,
)


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Library Schemas ---

class LibraryCreate(BaseSchema):
    name: str
    root_path: str
    watch_for_changes: bool = True


class LibraryUpdate(BaseSchema):
    name: Optional[str] = None
    root_path: Optional[str] = None
    watch_for_changes: Optional[bool] = None


class LibraryRead(BaseSchema):
    id: int
    name: str
    root_path: str
    watch_for_changes: bool
    created_at: datetime


# --- ExtraFile Schemas ---

class ExtraFileRead(BaseSchema):
    id: int
    media_item_id: int
    relative_path: str
    filename: str
    extension: str
    category: ExtraCategory
    subtype: Optional[ExtraSubtype] = None
    language: Optional[str] = None
    file_hash: Optional[str] = None


# --- MediaItem Schemas ---

class MediaItemRead(BaseSchema):
    id: int
    library_id: int
    relative_path: str
    folder_name: Optional[str] = None
    filename: str
    extension: str
    size: int
    mtime: Optional[float] = None
    hash_md5: Optional[str] = None
    hash_oshash: Optional[str] = None
    hash_phash: Optional[str] = None
    hash_sha256: Optional[str] = None
    group_hash: Optional[str] = None
    part_number: Optional[int] = None
    total_parts: Optional[int] = None
    internal_title: Optional[str] = None
    nfo_imdb_id: Optional[str] = None
    parsed_info: Optional[dict[str, Any]] = None
    duration: Optional[float] = None
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    video_bitrate: Optional[int] = None
    framerate: Optional[str] = None
    bit_depth: Optional[int] = None
    hdr_type: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_channels: Optional[str] = None
    audio_bitrate: Optional[int] = None
    audio_streams: Optional[List[dict]] = None
    subtitle_streams: Optional[List[dict]] = None
    edition: MovieEdition
    audio_type: MediaAudioType
    source: MediaSource
    status: ItemStatus
    ignored_previous_status: Optional[ItemStatus] = None
    ignored_at: Optional[datetime] = None
    planned_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# --- Legacy Endpoints Request and Response Schemas ---
# NOTE: Override schemas (ItemOverridesUpdate, BulkOverridesUpdate, etc.)
# have been moved to app.domains.users.schemas where UserOverride model lives.


class GenericSuccessResponse(BaseSchema):
    status: str = "success"
    message: Optional[str] = None


class BulkActionResponse(BaseSchema):
    status: str = "success"
    count: int = 0


# --- DTO Response Schemas ---

class LibraryStatsBreakdown(BaseModel):
    movies: str
    tv: str
    scenes: str
    extras: str

class ManualReviewBreakdown(BaseModel):
    new: int
    error: int
    uncertain: int
    no_match: int
    multiple: int

class GenreConstellationNode(BaseModel):
    id: str
    label: str
    count: int

class GenreConstellationLink(BaseModel):
    source: str
    target: str
    count: int

class GenreConstellation(BaseModel):
    nodes: List[GenreConstellationNode]
    links: List[GenreConstellationLink]

class LibraryStatsResponse(BaseModel):
    total_movies: int
    total_tv: int
    total_episodes: int
    total_scenes: int
    storage: str
    drive_count: int
    unmatched: int
    storage_breakdown: LibraryStatsBreakdown
    manual_review_total: int
    manual_review_breakdown: ManualReviewBreakdown
    genre_distribution: Dict[str, int]
    genre_distribution_ids: Dict[str, int]
    genre_labels: Dict[str, str]
    genre_constellation: GenreConstellation
    decade_distribution: Dict[str, int]

class ContinueWatchingItem(BaseModel):
    id: int
    title: str
    tv_title: Optional[str] = None
    episode_title: Optional[str] = None
    type: str
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    tv_tmdb_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    backdrop_path: Optional[str] = None
    still_path: Optional[str] = None
    resume_position: int
    duration: int
    is_watched: bool
    last_watched_at: Optional[str] = None

class LibraryTabItem(BaseModel):
    id: Optional[int] = None
    title: str
    year: Optional[int] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    rating: float
    rating_porndb: Optional[float] = None
    rating_imdb: Optional[float] = None
    type: str
    path: Optional[str] = None
    duration: float
    size: int

class LibraryTabCounts(BaseModel):
    movies: int
    tv: int
    scenes: int
    people: int

class LibraryTabResponse(BaseModel):
    tab: str
    items: List[LibraryTabItem]
    counts: LibraryTabCounts
    owned_counts: LibraryTabCounts
    total_items: int
    page: int
    page_size: int
    total_pages: int

class GroupedLibraryResponse(BaseModel):
    movies: List[LibraryTabItem]
    tv: List[LibraryTabItem]
    scenes: List[LibraryTabItem]
    people: List[Any]
    counts: LibraryTabCounts

class TagItem(BaseModel):
    id: int
    name: str
    color: Optional[str] = None
    is_adult: bool

class TagGroupItem(BaseModel):
    id: int
    name: str
    tags: List[TagItem]

class FilterOptionsResponse(BaseModel):
    genres: List[str]
    years: List[int]
    tags: List[TagItem]

# --- Dynamic Detail Response DTOs ---

class MovieDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str

class TvShowDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str

class TvSeasonDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str

class CollectionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str

class SceneDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str

class MovieCollectionItem(BaseModel):
    tmdb_id: int
    title: str
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    owned_count: int
    total_count: Optional[int] = None
    type: str = "collection"

class MovieCollectionsResponse(BaseModel):
    items: List[MovieCollectionItem]
    total_items: int
    page: int
    page_size: Optional[int] = None
    total_pages: int


