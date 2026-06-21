from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import String, Integer, DateTime, JSON, Boolean, ForeignKey, Table, Column, Enum as SQLEnum, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base
from app.shared_kernel.enums import MovieEdition, MediaAudioType, MediaSource, CustomListType


# Association table for UserOverride many-to-many relationship with Tag
user_override_tags = Table(
    "user_override_tags",
    Base.metadata,
    Column("user_override_id", Integer, ForeignKey("user_overrides.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True)
)


class User(Base):
    """
    Central user account table. Enables multi-user preferences, custom lists,
    playback logs, and serves as the single-sign-on anchor for dating/social modules.
    """
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member', 'child')", name="ck_users_role"),
        CheckConstraint("role != 'child' OR allow_adult = 0", name="ck_child_cannot_allow_adult"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pin_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="member", index=True)
    managed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_adult: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    managed_by: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side=[id],
        back_populates="managed_profiles",
    )
    managed_profiles: Mapped[List["User"]] = relationship(
        "User",
        back_populates="managed_by",
    )
    overrides: Mapped[List["UserOverride"]] = relationship("UserOverride", back_populates="user", cascade="all, delete-orphan")
    custom_lists: Mapped[List["CustomList"]] = relationship("CustomList", back_populates="user", cascade="all, delete-orphan")
    playback_logs: Mapped[List["PlaybackLog"]] = relationship("PlaybackLog", back_populates="user", cascade="all, delete-orphan")
    settings: Mapped[List["UserSetting"]] = relationship("UserSetting", back_populates="user", cascade="all, delete-orphan")


class Tag(Base):
    """
    Global user-defined tags that can be SFW or NSFW (is_adult).
    """
    __tablename__ = "tags"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    color: Mapped[Optional[str]] = mapped_column(String, default="#3b82f6") # Hex color code for UI
    is_adult: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # Tag separation SFW vs NSFW
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # User overrides for the three image slots
    custom_image_backdrop: Mapped[Optional[str]] = mapped_column(String)
    custom_image_poster_1: Mapped[Optional[str]] = mapped_column(String)
    custom_image_poster_2: Mapped[Optional[str]] = mapped_column(String)
    
    # Relationships
    overrides: Mapped[List["UserOverride"]] = relationship(
        "UserOverride", secondary=user_override_tags, back_populates="tags"
    )


class UserOverride(Base):
    """
    Stores all manual user adjustments. This isolates user data completely
    from incoming scraped data so that rescrapes NEVER overwrite user edits.
    """
    __tablename__ = "user_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "media_item_id", name="uq_user_media_item"),
        UniqueConstraint("user_id", "metadata_match_id", name="uq_user_metadata_match"),
        UniqueConstraint("user_id", "person_id", name="uq_user_person"),
        UniqueConstraint("user_id", "studio_id", name="uq_user_studio"),
        UniqueConstraint("user_id", "collection_id", name="uq_user_collection"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=1, index=True)
    
    media_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), nullable=True)
    metadata_match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), nullable=True)
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=True)
    studio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("studios.id", ondelete="CASCADE"), nullable=True)
    collection_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_collections.id", ondelete="CASCADE"), nullable=True)
    
    custom_title: Mapped[Optional[str]] = mapped_column(String)
    custom_overview: Mapped[Optional[str]] = mapped_column(String)
    custom_poster: Mapped[Optional[str]] = mapped_column(String)
    custom_backdrop: Mapped[Optional[str]] = mapped_column(String)
    custom_logo: Mapped[Optional[str]] = mapped_column(String) # For custom studio/performer logos
    custom_language: Mapped[Optional[str]] = mapped_column(String) # Custom per-item language override (e.g. 'hu')
    custom_edition: Mapped[Optional[MovieEdition]] = mapped_column(SQLEnum(MovieEdition), nullable=True)
    custom_audio_type: Mapped[Optional[MediaAudioType]] = mapped_column(SQLEnum(MediaAudioType), nullable=True)
    custom_source: Mapped[Optional[MediaSource]] = mapped_column(SQLEnum(MediaSource), nullable=True)
    
    user_rating: Mapped[Optional[int]] = mapped_column(Integer)
    user_rating_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    user_comment: Mapped[Optional[str]] = mapped_column(String)
    user_comment_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_favorite_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    is_watched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_watched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    watch_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    resume_position: Mapped[int] = mapped_column(Integer, default=0)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # For watchlist / virtual tracking SFW or NSFW
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="overrides")
    media_item: Mapped[Optional["MediaItem"]] = relationship("MediaItem", back_populates="overrides")
    metadata_match: Mapped[Optional["MetadataMatch"]] = relationship("MetadataMatch", back_populates="overrides")
    person: Mapped[Optional["Person"]] = relationship("Person", back_populates="overrides")
    studio: Mapped[Optional["Studio"]] = relationship("Studio", back_populates="overrides")
    collection: Mapped[Optional["MediaCollection"]] = relationship("MediaCollection", back_populates="overrides")
    tags: Mapped[List["Tag"]] = relationship(
        "Tag", secondary=user_override_tags, back_populates="overrides"
    )


class CustomList(Base):
    """User-defined collections (e.g., 'Favorite Sci-Fi', 'To Watch on Weekend')."""
    __tablename__ = "custom_lists"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=1, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(String)
    list_type: Mapped[CustomListType] = mapped_column(SQLEnum(CustomListType), default=CustomListType.MEDIA, index=True)
    color: Mapped[Optional[str]] = mapped_column(String) # For UI customization
    icon: Mapped[Optional[str]] = mapped_column(String)  # For UI customization
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship("User", back_populates="custom_lists")
    items: Mapped[List["CustomListItem"]] = relationship(
        "CustomListItem", back_populates="custom_list", cascade="all, delete-orphan"
    )


class CustomListItem(Base):
    """
    Items inside a custom list. Can link to a physical file, virtual match, performer, studio, or collection.
    """
    __tablename__ = "custom_list_items"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("custom_lists.id", ondelete="CASCADE"), index=True)
    media_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), nullable=True, index=True)
    match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), nullable=True, index=True)
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), nullable=True, index=True)
    studio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("studios.id", ondelete="CASCADE"), nullable=True, index=True)
    collection_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_collections.id", ondelete="CASCADE"), nullable=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    
    custom_list: Mapped["CustomList"] = relationship(back_populates="items")
    media_item: Mapped[Optional["MediaItem"]] = relationship("MediaItem")
    match: Mapped[Optional["MetadataMatch"]] = relationship("MetadataMatch")
    person: Mapped[Optional["Person"]] = relationship("Person")
    studio: Mapped[Optional["Studio"]] = relationship("Studio")
    collection: Mapped[Optional["MediaCollection"]] = relationship("MediaCollection")
