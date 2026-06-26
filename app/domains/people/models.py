from typing import List, Optional, Any
from sqlalchemy import String, Integer, Float, Enum as SQLEnum, JSON, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base
from app.shared_kernel.enums import RoleType, Provider


class Person(Base):
    """
    Global cast/crew database entry. Can be referenced by mainstream and adult matches.
    Supports extended metadata for mainstream alternative names and adult performer attributes.
    """
    __tablename__ = "people"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    aliases: Mapped[Optional[List[str]]] = mapped_column(JSON) # Alternative names (also_known_as / aliases)
    birthday: Mapped[Optional[str]] = mapped_column(String)
    deathday: Mapped[Optional[str]] = mapped_column(String)
    place_of_birth: Mapped[Optional[str]] = mapped_column(String)
    gender: Mapped[Optional[int]] = mapped_column(Integer)
    known_for_department: Mapped[Optional[str]] = mapped_column(String, index=True) # e.g. "Acting", "Directing"
    popularity: Mapped[Optional[float]] = mapped_column(Float)
    rating_porndb: Mapped[Optional[float]] = mapped_column(Float, index=True)
    scene_count: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    profile_path: Mapped[Optional[str]] = mapped_column(String)
    local_profile_path: Mapped[Optional[str]] = mapped_column(String) # Local path to cached profile image
    homepage: Mapped[Optional[str]] = mapped_column(String)
    images: Mapped[Optional[List[str]]] = mapped_column(JSON) # List of alternative profile image URLs
    external_ids: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON) # {"tmdb": "123", "stashdb": "uuid-xyz"}
    socials: Mapped[Optional[dict[str, str]]] = mapped_column(JSON) # Social media handles/links (e.g. instagram, twitter)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # True if the person has local files or user interaction
    is_adult: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # Extended/Adult Performer attributes (allows structured filtering)
    hair_color: Mapped[Optional[str]] = mapped_column(String, index=True)
    eye_color: Mapped[Optional[str]] = mapped_column(String)
    ethnicity: Mapped[Optional[str]] = mapped_column(String, index=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, index=True) # in cm
    weight: Mapped[Optional[int]] = mapped_column(Integer) # in kg
    measurements: Mapped[Optional[str]] = mapped_column(String) # e.g., "34B-24-34"
    cup_size: Mapped[Optional[str]] = mapped_column(String, index=True)
    tattoos: Mapped[Optional[str]] = mapped_column(String)
    piercings: Mapped[Optional[str]] = mapped_column(String)
    orientation: Mapped[Optional[str]] = mapped_column(String, index=True)
    
    # Career & Origin details
    career_start_year: Mapped[Optional[int]] = mapped_column(Integer)
    career_end_year: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Relationships
    media_links: Mapped[List["MediaPersonLink"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    localizations: Mapped[List["PersonLocalization"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    external_links: Mapped[List["ExternalSourceLink"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class PersonLocalization(Base):
    """
    Multi-language metadata for actors/performers (e.g. biography).
    """
    __tablename__ = "person_localizations"
    __table_args__ = (UniqueConstraint("person_id", "locale", name="uq_person_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    locale: Mapped[str] = mapped_column(String, default="en", index=True) # "hu", "en"
    
    biography: Mapped[Optional[str]] = mapped_column(String)
    
    # Relationships
    person: Mapped["Person"] = relationship(back_populates="localizations")


class MediaPersonLink(Base):
    """
    Link mapping people to movies/shows/scenes with roles.
    """
    __tablename__ = "media_person_links"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("metadata_matches.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    role: Mapped[RoleType] = mapped_column(SQLEnum(RoleType), index=True) # Actor, Director, etc.
    character_name: Mapped[Optional[str]] = mapped_column(String)
    order: Mapped[int] = mapped_column(Integer, default=0) # Order of appearance in cast list
    
    # Relationships
    person: Mapped["Person"] = relationship(back_populates="media_links")
    match: Mapped["MetadataMatch"] = relationship(back_populates="people_links")


class ExternalSourceLink(Base):
    """
    Links multiple external APIs to a single Person.
    Allows merging TMDB, StashDB, and PornDB profiles for the same actor.
    """
    __tablename__ = "external_source_links"
    __table_args__ = (UniqueConstraint("person_id", "provider", "external_id", name="uq_person_external_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    external_id: Mapped[str] = mapped_column(String, index=True) # e.g., StashDB performer UUID
    profile_url: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    person: Mapped["Person"] = relationship(back_populates="external_links")
