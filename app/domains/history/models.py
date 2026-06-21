from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, Enum as SQLEnum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base
from app.shared_kernel.enums import ActionType, ActionStatus

class PlaybackLog(Base):
    """Every time a user plays a file, a log entry is created."""
    __tablename__ = "playback_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=1, index=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), index=True)
    watched_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    position_seconds: Mapped[int] = mapped_column(Integer, default=0) # Last playback position
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="playback_logs")
    media_item: Mapped["MediaItem"] = relationship("MediaItem", back_populates="playback_logs")


class PlaybackPeakLog(Base):
    """Tracks climax / hot-spots / peak moments marked by the user."""
    __tablename__ = "playback_peak_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=1, index=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), index=True)
    video_position: Mapped[int] = mapped_column(Integer) # Position in seconds
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ActionBatch(Base):
    """Represents a group of file/metadata operations executed together (enables Undo/Redo)."""
    __tablename__ = "action_batches"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=1, index=True)
    name: Mapped[Optional[str]] = mapped_column(String) # e.g. "Rename Season 1"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    logs: Mapped[List["ActionLog"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class ActionLog(Base):
    """Audit log for individual operations (renaming, moving, deleting, matching files)."""
    __tablename__ = "action_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("action_batches.id", ondelete="CASCADE"), index=True)
    media_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_items.id", ondelete="SET NULL"), nullable=True, index=True)
    extra_file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("extra_files.id", ondelete="SET NULL"), nullable=True, index=True)
    
    action_type: Mapped[ActionType] = mapped_column(SQLEnum(ActionType), index=True)
    status: Mapped[ActionStatus] = mapped_column(SQLEnum(ActionStatus), default=ActionStatus.SUCCESS, index=True)
    
    old_value: Mapped[Optional[str]] = mapped_column(String) # e.g. original path/filename
    new_value: Mapped[Optional[str]] = mapped_column(String) # e.g. target path/filename
    error_message: Mapped[Optional[str]] = mapped_column(String)
    details: Mapped[Optional[dict]] = mapped_column(JSON) # e.g. detailed changes/metadata dict
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    batch: Mapped["ActionBatch"] = relationship(back_populates="logs")
    media_item: Mapped[Optional["MediaItem"]] = relationship("MediaItem")
    extra_file: Mapped[Optional["ExtraFile"]] = relationship("ExtraFile")
