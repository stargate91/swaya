from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import String, Integer, Float, DateTime, Enum as SQLEnum, JSON, Boolean, ForeignKey, UniqueConstraint, Table, Column, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base
from app.shared_kernel.enums import Provider, MediaType


# Association table for MetadataMatch many-to-many relationship with Studio/Company/Network
metadata_match_studios = Table(
    "metadata_match_studios",
    Base.metadata,
    Column("metadata_match_id", Integer, ForeignKey("metadata_matches.id", ondelete="CASCADE"), primary_key=True),
    Column("studio_id", Integer, ForeignKey("studios.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("relation_type", String, default="studio", index=True) # e.g. "network", "production_company", "studio"
)


class Studio(Base):
    """
    Production studio or network. Supports hierarchical structures
    (e.g., Network/Parent Studio -> Sub-studio/Site).
    """
    __tablename__ = "studios"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String)
    
    # Self-referential hierarchy
    parent_studio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("studios.id", ondelete="SET NULL"), index=True)
    
    # Relationships
    parent_studio: Mapped[Optional["Studio"]] = relationship("Studio", remote_side=[id], back_populates="sub_studios")
    sub_studios: Mapped[List["Studio"]] = relationship("Studio", back_populates="parent_studio")
    matches: Mapped[List["MetadataMatch"]] = relationship("MetadataMatch", secondary=metadata_match_studios, back_populates="studios")
    overrides: Mapped[Optional["UserOverride"]] = relationship("UserOverride", back_populates="studio", cascade="all, delete-orphan")
    external_links: Mapped[List["ExternalStudioLink"]] = relationship("ExternalStudioLink", back_populates="studio", cascade="all, delete-orphan")


class MetadataMatch(Base):
    """
    Level 2: The external scraper match record from TMDB, StashDB, etc.
    """
    __tablename__ = "metadata_matches"
    __table_args__ = (UniqueConstraint("media_item_id", "provider", "external_id", "media_type", name="uq_provider_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    media_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), nullable=True, index=True) # Self-referential link for TV -> Season -> Episode
    collection_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_collections.id", ondelete="SET NULL"), nullable=True, index=True)
    
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True) # e.g. TMDB Movie ID (int) or StashDB Scene UUID
    media_type: Mapped[MediaType] = mapped_column(SQLEnum(MediaType), index=True)
    season_number: Mapped[Optional[int]] = mapped_column(Integer) # For TV Season number
    episode_number: Mapped[Optional[Any]] = mapped_column(JSON) # For TV Episode number (JSON to support double episodes like [1, 2])
    number_of_seasons: Mapped[Optional[int]] = mapped_column(Integer) # Total seasons count (for TV shows)
    number_of_episodes: Mapped[Optional[int]] = mapped_column(Integer) # Total episodes count (for TV shows)
    
    rating_tmdb: Mapped[Optional[float]] = mapped_column(Float)
    rating_porndb: Mapped[Optional[float]] = mapped_column(Float, index=True)
    rating_imdb: Mapped[Optional[float]] = mapped_column(Float, index=True)
    rating_rotten: Mapped[Optional[str]] = mapped_column(String) # e.g. "85%"
    rating_meta: Mapped[Optional[int]] = mapped_column(Integer)
    vote_count_tmdb: Mapped[Optional[int]] = mapped_column(Integer)
    vote_count_imdb: Mapped[Optional[int]] = mapped_column(Integer)
    budget: Mapped[Optional[int]] = mapped_column(BigInteger)
    revenue: Mapped[Optional[int]] = mapped_column(BigInteger)
    release_status: Mapped[Optional[str]] = mapped_column(String)
    tv_type: Mapped[Optional[str]] = mapped_column(String)
    
    release_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True) # Premier/First air date / Episode air date
    last_air_date: Mapped[Optional[datetime]] = mapped_column(DateTime) # End date for TV shows (if finished)
    popularity: Mapped[Optional[float]] = mapped_column(Float, index=True) # Popularity score for sorting
    runtime: Mapped[Optional[int]] = mapped_column(Integer) # Official runtime in minutes
    imdb_id: Mapped[Optional[str]] = mapped_column(String, index=True) # Global cross-reference ID (e.g. tt1234567)
    original_title: Mapped[Optional[str]] = mapped_column(String, index=True) # Original movie/tv title for searching
    backdrop_path: Mapped[Optional[str]] = mapped_column(String) # Language-independent background image
    local_backdrop_path: Mapped[Optional[str]] = mapped_column(String) # Local path to cached background image
    still_path: Mapped[Optional[str]] = mapped_column(String) # Language-independent single still image (for episodes)
    local_still_path: Mapped[Optional[str]] = mapped_column(String) # Local path to cached still image
    suggested_tags: Mapped[Optional[List[str]]] = mapped_column(JSON) # List of scraper-provided tags for UI suggestions
    stills: Mapped[Optional[List[str]]] = mapped_column(JSON) # Alternative screenshots / episode preview images (language-independent)
    local_stills: Mapped[Optional[List[str]]] = mapped_column(JSON) # Local paths to cached alternative screenshots
    fetched_locales: Mapped[Optional[List[str]]] = mapped_column(JSON) # List of languages/locales already fetched or attempted
    raw_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON) # Raw JSON payload for non-critical query fields
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_adult: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # SFW / NSFW content flag for safe filtering
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0) # Match accuracy confidence (0.0 to 1.0)
    
    # Relationships
    media_item: Mapped[Optional["MediaItem"]] = relationship("MediaItem", back_populates="matches")
    parent: Mapped[Optional["MetadataMatch"]] = relationship("MetadataMatch", remote_side=[id], back_populates="children")
    children: Mapped[List["MetadataMatch"]] = relationship("MetadataMatch", back_populates="parent", cascade="all, delete-orphan")
    collection: Mapped[Optional["MediaCollection"]] = relationship("MediaCollection", back_populates="matches")
    localizations: Mapped[List["MetadataLocalization"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    studios: Mapped[List["Studio"]] = relationship("Studio", secondary=metadata_match_studios, back_populates="matches")
    overrides: Mapped[Optional["UserOverride"]] = relationship("UserOverride", back_populates="metadata_match", cascade="all, delete-orphan")
    external_links: Mapped[List["ExternalMatchLink"]] = relationship("ExternalMatchLink", back_populates="match", cascade="all, delete-orphan")
    people_links: Mapped[List["MediaPersonLink"]] = relationship("MediaPersonLink", back_populates="match", cascade="all, delete-orphan")


class MetadataLocalization(Base):
    """
    Level 3: Multi-language text/image support linked to the metadata match.
    """
    __tablename__ = "metadata_localizations"
    __table_args__ = (UniqueConstraint("match_id", "locale", name="uq_match_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), index=True)
    locale: Mapped[str] = mapped_column(String, default="en", index=True) # "hu", "en", etc.
    
    title: Mapped[str] = mapped_column(String)
    tagline: Mapped[Optional[str]] = mapped_column(String)
    overview: Mapped[Optional[str]] = mapped_column(String)
    poster_path: Mapped[Optional[str]] = mapped_column(String)
    local_poster_path: Mapped[Optional[str]] = mapped_column(String) # Local path to cached poster
    logo_path: Mapped[Optional[str]] = mapped_column(String) # Language-dependent clear logo / title art
    local_logo_path: Mapped[Optional[str]] = mapped_column(String) # Local path to cached logo
    trailer_url: Mapped[Optional[str]] = mapped_column(String)
    
    # Language/Origin details
    origin_country: Mapped[Optional[List[str]]] = mapped_column(JSON)
    original_language: Mapped[Optional[str]] = mapped_column(String)
    spoken_languages: Mapped[Optional[List[str]]] = mapped_column(JSON)
    genres: Mapped[Optional[List[str]]] = mapped_column(JSON) # Localized list of genres (e.g. ["Action", "Sci-Fi"])
    
    # Relationships
    match: Mapped["MetadataMatch"] = relationship(back_populates="localizations")


class EntityRelation(Base):
    """
    Handles relations between matches across different providers or media types.
    Enables linking StashDB Scenes to TMDB Movies, or spin-offs/extras.
    """
    __tablename__ = "entity_relations"
    __table_args__ = (UniqueConstraint("parent_match_id", "child_match_id", "relation_type", name="uq_entity_relation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_match_id: Mapped[int] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), index=True)
    child_match_id: Mapped[int] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String, default="scene_in_movie", index=True) # e.g., "scene_in_movie", "spin_off", "extras"
    
    # Relationships
    parent: Mapped["MetadataMatch"] = relationship("MetadataMatch", foreign_keys=[parent_match_id])
    child: Mapped["MetadataMatch"] = relationship("MetadataMatch", foreign_keys=[child_match_id])


class MediaCollection(Base):
    """
    Represents a collection or saga of matches (e.g. Harry Potter Collection).
    """
    __tablename__ = "media_collections"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_collection_provider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    backdrop_path: Mapped[Optional[str]] = mapped_column(String)
    local_backdrop_path: Mapped[Optional[str]] = mapped_column(String)
    
    # Relationships
    matches: Mapped[List["MetadataMatch"]] = relationship("MetadataMatch", back_populates="collection")
    localizations: Mapped[List["MediaCollectionLocalization"]] = relationship(back_populates="collection", cascade="all, delete-orphan")
    overrides: Mapped[Optional["UserOverride"]] = relationship("UserOverride", back_populates="collection", cascade="all, delete-orphan")
    external_links: Mapped[List["ExternalCollectionLink"]] = relationship("ExternalCollectionLink", back_populates="collection", cascade="all, delete-orphan")


class MediaCollectionLocalization(Base):
    """
    Multi-language support for collections (localized title, overview, poster).
    """
    __tablename__ = "media_collection_localizations"
    __table_args__ = (UniqueConstraint("collection_id", "locale", name="uq_collection_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("media_collections.id", ondelete="CASCADE"), index=True)
    locale: Mapped[str] = mapped_column(String, default="en", index=True) # "hu", "en", etc.
    
    title: Mapped[str] = mapped_column(String)
    overview: Mapped[Optional[str]] = mapped_column(String)
    poster_path: Mapped[Optional[str]] = mapped_column(String)
    local_poster_path: Mapped[Optional[str]] = mapped_column(String) # Local path to cached poster
    
    # Relationships
    collection: Mapped["MediaCollection"] = relationship(back_populates="localizations")


class ExternalMatchLink(Base):
    """
    Links multiple external APIs to a single MetadataMatch.
    Allows linking a match to IMDb, TMDB, StashDB, etc. simultaneously.
    """
    __tablename__ = "external_match_links"
    __table_args__ = (UniqueConstraint("match_id", "provider", "external_id", name="uq_match_external_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), index=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    match: Mapped["MetadataMatch"] = relationship("MetadataMatch", back_populates="external_links")


class ExternalStudioLink(Base):
    """
    Links multiple external APIs to a single Studio.
    """
    __tablename__ = "external_studio_links"
    __table_args__ = (UniqueConstraint("studio_id", "provider", "external_id", name="uq_studio_external_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    studio_id: Mapped[int] = mapped_column(ForeignKey("studios.id", ondelete="CASCADE"), index=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    studio: Mapped["Studio"] = relationship("Studio", back_populates="external_links")


class ExternalCollectionLink(Base):
    """
    Links multiple external APIs to a single MediaCollection.
    """
    __tablename__ = "external_collection_links"
    __table_args__ = (UniqueConstraint("collection_id", "provider", "external_id", name="uq_collection_external_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("media_collections.id", ondelete="CASCADE"), index=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    collection: Mapped["MediaCollection"] = relationship("MediaCollection", back_populates="external_links")
