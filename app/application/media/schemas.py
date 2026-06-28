from pydantic import BaseModel
from typing import Optional, List, Union

class PlayMediaRequest(BaseModel):
    item_id: Union[str, int]

class PreviewMediaRequest(BaseModel):
    file_path: str
    start_seconds: Optional[float] = 0.0

class PathPayloadRequest(BaseModel):
    path: str

class WatchHistoryPayload(BaseModel):
    watched_at: Optional[str] = None

class PlaybackStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    player_type: Optional[str] = None
    port: Optional[int] = None
    resume_position: Optional[int] = None
    is_watched: Optional[bool] = None

class PlaybackLogDto(BaseModel):
    id: int
    watched_at: str

class WatchHistoryResponse(BaseModel):
    status: str
    watch_count: int
    is_watched: bool
    resume_position: int
    last_watched_at: Optional[str] = None
    playback_logs: List[PlaybackLogDto]

class WatchedHistoryItem(BaseModel):
    id: int
    media_item_id: int
    watched_at: str
    title: str
    type: str
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    resume_position: int
    duration: int
    is_watched: bool
    is_active: Optional[bool] = False

class WatchedHistoryResponse(BaseModel):
    items: List[WatchedHistoryItem]
    page: int
    has_more: bool
