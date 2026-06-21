from datetime import datetime
from typing import List, Optional, Any
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

