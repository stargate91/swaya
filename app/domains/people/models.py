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
    primary_provider: Mapped[Optional[Provider]] = mapped_column(SQLEnum(Provider), nullable=True)
    field_routing: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)
    
    # Extended/Adult Performer attributes (allows structured filtering)
    hair_color: Mapped[Optional[str]] = mapped_column(String, index=True)
    eye_color: Mapped[Optional[str]] = mapped_column(String)
    ethnicity: Mapped[Optional[str]] = mapped_column(String, index=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, index=True) # in cm
    weight: Mapped[Optional[int]] = mapped_column(Integer) # in kg
    measurements: Mapped[Optional[str]] = mapped_column(String) # e.g., "34B-24-34"
    cup_size: Mapped[Optional[str]] = mapped_column(String, index=True)
    band_size: Mapped[Optional[int]] = mapped_column(Integer)
    waist: Mapped[Optional[int]] = mapped_column(Integer)
    hip: Mapped[Optional[int]] = mapped_column(Integer)
    breast_type: Mapped[Optional[str]] = mapped_column(String, index=True)
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

    def recalculate_projection(self, db):
        priority_map = {
            Provider.TMDB: 4,
            Provider.STASHDB: 3,
            Provider.FANSDB: 2,
            Provider.PORNDB: 1
        }
        if self.primary_provider:
            priority_map[self.primary_provider] = 10
        
        sorted_links = sorted(
            self.external_links,
            key=lambda l: priority_map.get(l.provider, 0)
        )
        
        routing = dict(self.field_routing or {})

        def get_val(field_name, default_val=None):
            routed_provider = routing.get(field_name)
            if routed_provider:
                for link in self.external_links:
                    if link.provider.value == routed_provider and link.source_data:
                        val = link.source_data.get(field_name)
                        if val is not None and val != "":
                            return val
            # Fallback to priority loop (highest priority link overwrites lower)
            for link in sorted_links:
                data = link.source_data
                if not data:
                    continue
                val = data.get(field_name)
                if val is not None and val != "":
                    default_val = val
            return default_val

        birthday = get_val("birthday")
        deathday = get_val("deathday")
        place_of_birth = get_val("place_of_birth")
        gender = get_val("gender")
        known_for_department = get_val("known_for_department", self.known_for_department or ("Acting" if self.is_adult else None))
        popularity = get_val("popularity")
        rating_porndb = get_val("rating_porndb")
        scene_count = get_val("scene_count")
        profile_path = get_val("profile_path", self.profile_path)
        homepage = get_val("homepage")
        
        hair_color = get_val("hair_color")
        eye_color = get_val("eye_color")
        ethnicity = get_val("ethnicity")
        height = get_val("height")
        weight = get_val("weight")
        measurements = get_val("measurements")
        cup_size = get_val("cup_size")
        band_size = get_val("band_size")
        waist = get_val("waist")
        hip = get_val("hip")
        tattoos = get_val("tattoos")
        piercings = get_val("piercings")
        orientation = get_val("orientation")
        breast_type = get_val("breast_type")
        career_start_year = get_val("career_start_year")
        career_end_year = get_val("career_end_year")
        
        images = []
        aliases = []
        socials = {}
        
        # Merge multi-value structures from all providers
        for link in sorted_links:
            data = link.source_data
            if not data:
                continue
            if data.get("images"):
                for img in data["images"]:
                    if img not in images:
                        images.append(img)
            if data.get("aliases"):
                for alias in data["aliases"]:
                    if alias not in aliases:
                        aliases.append(alias)
            if data.get("socials"):
                socials.update(data["socials"])

        # Resolve biography locales
        biographies = {}
        routed_bio_provider = routing.get("biography")
        if routed_bio_provider:
            for link in self.external_links:
                if link.provider.value == routed_bio_provider and link.source_data:
                    data = link.source_data
                    if data.get("biographies"):
                        for loc, bio_text in data["biographies"].items():
                            if bio_text:
                                biographies[loc] = bio_text
        if not biographies:
            for link in sorted_links:
                data = link.source_data
                if not data or not data.get("biographies"):
                    continue
                for loc, bio_text in data["biographies"].items():
                    if bio_text:
                        biographies[loc] = bio_text
        
        if birthday: self.birthday = birthday
        if deathday: self.deathday = deathday
        if place_of_birth: self.place_of_birth = place_of_birth
        if gender is not None: self.gender = gender
        if known_for_department: self.known_for_department = known_for_department
        if popularity is not None: self.popularity = popularity
        if rating_porndb is not None: self.rating_porndb = rating_porndb
        if scene_count is not None: self.scene_count = scene_count
        if profile_path: self.profile_path = profile_path
        if homepage: self.homepage = homepage
        if images: self.images = images
        if aliases: self.aliases = aliases
        if socials: self.socials = socials
        
        if hair_color: self.hair_color = hair_color
        if eye_color: self.eye_color = eye_color
        if ethnicity: self.ethnicity = ethnicity
        if height is not None: self.height = height
        if weight is not None: self.weight = weight
        if measurements: self.measurements = measurements
        if cup_size: self.cup_size = cup_size
        if band_size is not None: self.band_size = band_size
        if waist is not None: self.waist = waist
        if hip is not None: self.hip = hip
        if tattoos: self.tattoos = tattoos
        if piercings: self.piercings = piercings
        if orientation: self.orientation = orientation
        if breast_type: self.breast_type = breast_type
        if career_start_year is not None: self.career_start_year = career_start_year
        if career_end_year is not None: self.career_end_year = career_end_year
        
        ext_ids = dict(self.external_ids or {})
        for link in self.external_links:
            key = link.provider.value
            ext_ids[key] = str(link.external_id)
            ext_ids[f"{key}_id"] = str(link.external_id)
        active_providers = {link.provider.value for link in self.external_links}
        for provider_val in [Provider.TMDB.value, Provider.STASHDB.value, Provider.FANSDB.value, Provider.PORNDB.value]:
            if provider_val not in active_providers:
                ext_ids.pop(provider_val, None)
                ext_ids.pop(f"{provider_val}_id", None)
        self.external_ids = ext_ids
        
        existing_localizations = {l.locale: l for l in self.localizations}
        for loc, bio_text in biographies.items():
            if loc in existing_localizations:
                existing_localizations[loc].biography = bio_text
            else:
                from app.domains.people.models import PersonLocalization
                new_loc = PersonLocalization(person_id=self.id, locale=loc, biography=bio_text)
                db.add(new_loc)
                self.localizations.append(new_loc)
        for loc, loc_obj in list(existing_localizations.items()):
            if loc not in biographies:
                db.delete(loc_obj)


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
    source_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # Relationships
    person: Mapped["Person"] = relationship(back_populates="external_links")
