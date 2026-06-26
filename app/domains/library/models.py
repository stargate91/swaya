from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import String, Integer, Float, DateTime, Enum as SQLEnum, JSON, Boolean, ForeignKey, UniqueConstraint, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base
from app.shared_kernel.enums import ItemStatus, MovieEdition, MediaAudioType, MediaSource, ExtraCategory, ExtraSubtype


class Library(Base):
    """
    Core Level 1: Represents a watched directory root on the file system.
    Enables path relativization so that drive letter changes can be fixed instantly.
    """
    __tablename__ = "libraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    root_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    watch_for_changes: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    media_items: Mapped[List["MediaItem"]] = relationship("MediaItem", back_populates="library", cascade="all, delete-orphan")


class MediaItem(Base):
    """
    Core Level 1: Represents a physical file on the disk (video clip, scene, movie).
    Contains purely technical, filesystem, and codec specifications.
    """
    __tablename__ = "media_items"
    __table_args__ = (UniqueConstraint("library_id", "relative_path", name="uq_library_relative_path"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    library_id: Mapped[int] = mapped_column(ForeignKey("libraries.id", ondelete="CASCADE"), index=True)
    relative_path: Mapped[str] = mapped_column(String, nullable=False, index=True)
    folder_name: Mapped[Optional[str]] = mapped_column(String, index=True)

    filename: Mapped[str] = mapped_column(String, nullable=False, index=True)
    extension: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    mtime: Mapped[Optional[float]] = mapped_column(Float, index=True)

    hash_md5: Mapped[Optional[str]] = mapped_column(String, index=True)
    hash_oshash: Mapped[Optional[str]] = mapped_column(String, index=True)
    hash_phash: Mapped[Optional[str]] = mapped_column(String, index=True)
    hash_sha256: Mapped[Optional[str]] = mapped_column(String, index=True)
    group_hash: Mapped[Optional[str]] = mapped_column(String, index=True)
    part_number: Mapped[Optional[int]] = mapped_column(Integer)
    total_parts: Mapped[Optional[int]] = mapped_column(Integer)

    internal_title: Mapped[Optional[str]] = mapped_column(String)
    nfo_imdb_id: Mapped[Optional[str]] = mapped_column(String)
    parsed_info: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    duration: Mapped[Optional[float]] = mapped_column(Float)
    resolution: Mapped[Optional[str]] = mapped_column(String)
    video_codec: Mapped[Optional[str]] = mapped_column(String)
    video_bitrate: Mapped[Optional[int]] = mapped_column(Integer)
    framerate: Mapped[Optional[str]] = mapped_column(String)
    bit_depth: Mapped[Optional[int]] = mapped_column(Integer)
    hdr_type: Mapped[Optional[str]] = mapped_column(String)
    audio_codec: Mapped[Optional[str]] = mapped_column(String)
    audio_channels: Mapped[Optional[str]] = mapped_column(String)
    audio_bitrate: Mapped[Optional[int]] = mapped_column(Integer)
    audio_streams: Mapped[Optional[List[dict]]] = mapped_column(JSON)
    subtitle_streams: Mapped[Optional[List[dict]]] = mapped_column(JSON)

    edition: Mapped[MovieEdition] = mapped_column(SQLEnum(MovieEdition), default=MovieEdition.NONE, index=True)
    audio_type: Mapped[MediaAudioType] = mapped_column(SQLEnum(MediaAudioType), default=MediaAudioType.NONE, index=True)
    source: Mapped[MediaSource] = mapped_column(SQLEnum(MediaSource), default=MediaSource.NONE, index=True)

    custom_edition: Mapped[Optional[MovieEdition]] = mapped_column(SQLEnum(MovieEdition), nullable=True, index=True)
    custom_audio_type: Mapped[Optional[MediaAudioType]] = mapped_column(SQLEnum(MediaAudioType), nullable=True, index=True)
    custom_source: Mapped[Optional[MediaSource]] = mapped_column(SQLEnum(MediaSource), nullable=True, index=True)

    status: Mapped[ItemStatus] = mapped_column(SQLEnum(ItemStatus), default=ItemStatus.NEW, index=True)
    ignored_previous_status: Mapped[Optional[ItemStatus]] = mapped_column(SQLEnum(ItemStatus), nullable=True)
    ignored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    planned_path: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    library: Mapped["Library"] = relationship(back_populates="media_items")
    extras: Mapped[List["ExtraFile"]] = relationship(back_populates="media_item", cascade="all, delete-orphan")
    matches: Mapped[List["MetadataMatch"]] = relationship("MetadataMatch", back_populates="media_item", cascade="all, delete-orphan")
    overrides: Mapped[Optional["UserOverride"]] = relationship("UserOverride", back_populates="media_item", cascade="all, delete-orphan")
    playback_logs: Mapped[List["PlaybackLog"]] = relationship("PlaybackLog", back_populates="media_item", cascade="all, delete-orphan")

    @property
    def current_path(self) -> str:
        import os
        if os.path.isabs(self.relative_path):
            return os.path.normpath(self.relative_path)
        return os.path.normpath(os.path.join(self.library.root_path, self.relative_path))

    @current_path.setter
    def current_path(self, val: str):
        import os
        try:
            self.relative_path = os.path.relpath(val, self.library.root_path).replace("\\", "/")
        except ValueError:
            self.relative_path = os.path.normpath(val).replace("\\", "/")


class ExtraFile(Base):
    """
    Core Level 1: Associated files like subtitles, local images, and trailers.
    Keeps track of helper files accompanying the main media files.
    """
    __tablename__ = "extra_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_item_id: Mapped[int] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), index=True)
    relative_path: Mapped[str] = mapped_column(String, nullable=False, index=True)

    filename: Mapped[str] = mapped_column(String, nullable=False)
    extension: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[ExtraCategory] = mapped_column(SQLEnum(ExtraCategory), nullable=False, index=True)
    subtype: Mapped[Optional[ExtraSubtype]] = mapped_column(SQLEnum(ExtraSubtype), nullable=True, index=True)
    language: Mapped[Optional[str]] = mapped_column(String)
    file_hash: Mapped[Optional[str]] = mapped_column(String, index=True)

    media_item: Mapped["MediaItem"] = relationship(back_populates="extras")

    @property
    def current_path(self) -> str:
        import os
        if os.path.isabs(self.relative_path):
            return os.path.normpath(self.relative_path)
        return os.path.normpath(os.path.join(self.media_item.library.root_path, self.relative_path))

    @current_path.setter
    def current_path(self, val: str):
        import os
        try:
            self.relative_path = os.path.relpath(val, self.media_item.library.root_path).replace("\\", "/")
        except ValueError:
            self.relative_path = os.path.normpath(val).replace("\\", "/")
