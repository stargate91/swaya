from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from app.shared_kernel.enums import TaskStatus, TaskErrorCode, Provider

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class BackgroundTaskRead(BaseSchema):
    id: int
    user_id: Optional[int] = None
    name: str
    status: TaskStatus
    progress: float
    error_code: Optional[TaskErrorCode] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ScraperLogRead(BaseSchema):
    id: int
    task_id: Optional[int] = None
    media_item_id: Optional[int] = None
    provider: Provider
    search_query: str
    result_count: int
    details: Dict[str, Any]
    created_at: datetime

