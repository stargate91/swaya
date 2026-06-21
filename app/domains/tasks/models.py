from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Float, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base
from app.shared_kernel.enums import TaskStatus, TaskErrorCode, Provider


class BackgroundTask(Base):
    """
    Tracks long-running background processes (scanning, scraping, thumbnail generation)
    to enable per-session progress bars and job recovery.
    """
    __tablename__ = "background_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True) # e.g., "library_scan", "metadata_scraping"
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0) # Percentage from 0.0 to 100.0
    error_code: Mapped[Optional[TaskErrorCode]] = mapped_column(SQLEnum(TaskErrorCode), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")


class ScraperLog(Base):
    """
    Persists structured logs of scraper runs, query details, and scoring parameters for auditing.
    """
    __tablename__ = "scraper_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("background_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    media_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_items.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    search_query: Mapped[str] = mapped_column(String, index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


