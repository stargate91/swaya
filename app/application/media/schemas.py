from pydantic import BaseModel
from typing import Optional

class PlayMediaRequest(BaseModel):
    item_id: str

class PreviewMediaRequest(BaseModel):
    file_path: str
    start_seconds: Optional[float] = 0.0

class PathPayloadRequest(BaseModel):
    path: str

class WatchHistoryPayload(BaseModel):
    watched_at: Optional[str] = None
