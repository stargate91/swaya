import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType, RoleType
from app.domains.metadata.models import MetadataMatch, MetadataLocalization, Studio, MediaCollection
from app.domains.people.models import Person, MediaPersonLink
from app.domains.people.services import PersonService

logger = logging.getLogger(__name__)

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

import threading

persistence_lock = threading.Lock()

class ScraperPersister:
    """
    Handles database persistence for scraper metadata.
    Decoupled from scraper classes to maintain clean domain boundaries.
    """

    def __init__(self, db: Session):
        self.db = db

    def persist_normalized_scene(
        self,
        provider: Provider,
        scene_id: str,
        norm: Dict[str, Any],
        media_type: MediaType = MediaType.SCENE,
    ) -> MetadataMatch:
        """Takes a normalized scene structure and persists it to the database."""
        with persistence_lock:
            # Find or create match
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == provider,
                MetadataMatch.external_id == scene_id,
                MetadataMatch.media_type == media_type
            ).first()

            if not match:
                match = MetadataMatch(
                    provider=provider,
                    external_id=scene_id,
                    media_type=media_type
                )
                try:
                    with self.db.begin_nested():
                        self.db.add(match)
                        self.db.flush()
                except Exception:
                    match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == provider,
                        MetadataMatch.external_id == scene_id,
                        MetadataMatch.media_type == media_type
                    ).first()

            # 1. Map basic match fields
            for k, v in norm["match"].items():
                setattr(match, k, v)

            # 2. Map Studio details
            for studio_info in norm["studios"]:
                s_name = studio_info["name"]
                studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                if not studio:
                    studio = Studio(name=s_name, logo_path=studio_info["logo_path"])
                    try:
                        with self.db.begin_nested():
                            self.db.add(studio)
                            self.db.flush()
                    except Exception:
                        studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                
                # Map parent studio
                parent_info = studio_info["parent"]
                if parent_info:
                    p_name = parent_info["name"]
                    parent_studio = self.db.query(Studio).filter(Studio.name == p_name).first()
                    if not parent_studio:
                        parent_studio = Studio(name=p_name, logo_path=parent_info["logo_path"])
                        try:
                            with self.db.begin_nested():
                                self.db.add(parent_studio)
                                self.db.flush()
                        except Exception:
                            parent_studio = self.db.query(Studio).filter(Studio.name == p_name).first()
                    studio.parent_studio = parent_studio

                if studio not in match.studios:
                    match.studios.append(studio)

            loc = None
            for l in match.localizations:
                if l.locale == DEFAULT_FALLBACK_LANGUAGE:
                    loc = l
                    break
            if not loc:
                loc = self.db.query(MetadataLocalization).filter(
                    MetadataLocalization.match_id == match.id if match.id else False,
                    MetadataLocalization.locale == DEFAULT_FALLBACK_LANGUAGE
                ).first()
            if not loc:
                loc = MetadataLocalization(locale=DEFAULT_FALLBACK_LANGUAGE)
                for k, v in norm["localization"].items():
                    if k != "genres":
                        setattr(loc, k, v)
                match.localizations.append(loc)
                try:
                    with self.db.begin_nested():
                        self.db.flush()
                except Exception:
                    loc = self.db.query(MetadataLocalization).filter(
                        MetadataLocalization.match_id == match.id if match.id else False,
                        MetadataLocalization.locale == DEFAULT_FALLBACK_LANGUAGE
                    ).first()
            else:
                for k, v in norm["localization"].items():
                    if k != "genres":
                        setattr(loc, k, v)

            # 4. Map Performers/Cast utilizing PersonService
            person_service = PersonService(self.db)
            for idx, perf in enumerate(norm["performers"]):
                prov_enum = None
                if perf.get("provider"):
                    try:
                        prov_enum = Provider(perf["provider"])
                    except Exception:
                        pass
                person = person_service.update_or_create_person(
                    name=perf["name"],
                    profile_path=perf["profile_path"],
                    gender=perf["gender"],
                    is_adult=perf["is_adult"],
                    performer_details=perf["performer_details"],
                    provider=prov_enum,
                    external_id=perf.get("external_id")
                )

                # Link person to match
                link = self.db.query(MediaPersonLink).filter(
                    MediaPersonLink.match_id == match.id if match.id else False,
                    MediaPersonLink.person_id == person.id if person.id else False,
                    MediaPersonLink.role == RoleType.ACTOR
                ).first()

                if not link:
                    link = MediaPersonLink(
                        role=RoleType.ACTOR,
                        order=idx
                    )
                    link.person = person
                    match.people.append(link)

            self.db.flush()
            return match

    def persist_normalized_movie(self, movie_id: str, norm: Dict[str, Any], language: str) -> MetadataMatch:
        """Takes a normalized movie structure and persists it to the database."""
        with persistence_lock:
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.external_id == movie_id,
                MetadataMatch.media_type == MediaType.MOVIE
            ).first()

            if not match:
                match = MetadataMatch(
                    provider=Provider.TMDB,
                    external_id=movie_id,
                    media_type=MediaType.MOVIE
                )
                try:
                    with self.db.begin_nested():
                        self.db.add(match)
                        self.db.flush()
                except Exception:
                    match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == Provider.TMDB,
                        MetadataMatch.external_id == movie_id,
                        MetadataMatch.media_type == MediaType.MOVIE
                    ).first()

            # 1. Map basic match fields
            for k, v in norm["match"].items():
                setattr(match, k, v)

            # 2. Map Studio details
            for studio_info in norm["studios"]:
                s_name = studio_info["name"]
                studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                if not studio:
                    studio = Studio(name=s_name, logo_path=studio_info["logo_path"])
                    try:
                        with self.db.begin_nested():
                            self.db.add(studio)
                            self.db.flush()
                    except Exception:
                        studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                if studio not in match.studios:
                    match.studios.append(studio)

            # 3. Map Collection details
            coll_info = norm["collection"]
            if coll_info:
                coll_id = coll_info["external_id"]
                collection = self.db.query(MediaCollection).filter(
                    MediaCollection.provider == Provider.TMDB,
                    MediaCollection.external_id == coll_id
                ).first()
                if not collection:
                    collection = MediaCollection(
                        provider=Provider.TMDB,
                        external_id=coll_id,
                        backdrop_path=coll_info["backdrop_path"]
                    )
                    try:
                        with self.db.begin_nested():
                            self.db.add(collection)
                            self.db.flush()
                    except Exception:
                        collection = self.db.query(MediaCollection).filter(
                            MediaCollection.provider == Provider.TMDB,
                            MediaCollection.external_id == coll_id
                        ).first()
                match.collection = collection

            # 4. Map Localization
            loc = None
            for l in match.localizations:
                if l.locale == language:
                    loc = l
                    break
            if not loc:
                loc = self.db.query(MetadataLocalization).filter(
                    MetadataLocalization.match_id == match.id if match.id else False,
                    MetadataLocalization.locale == language
                ).first()
            if not loc:
                loc = MetadataLocalization(locale=language)
                for k, v in norm["localization"].items():
                    setattr(loc, k, v)
                match.localizations.append(loc)
                try:
                    with self.db.begin_nested():
                        self.db.flush()
                except Exception:
                    loc = self.db.query(MetadataLocalization).filter(
                        MetadataLocalization.match_id == match.id if match.id else False,
                        MetadataLocalization.locale == language
                    ).first()
            else:
                for k, v in norm["localization"].items():
                    setattr(loc, k, v)

            # 5. Map Cast/Crew utilizing PersonService
            person_service = PersonService(self.db)
            for idx, cast_member in enumerate(norm["performers"][:15]):
                person = person_service.update_or_create_person(
                    name=cast_member["name"],
                    profile_path=cast_member["profile_path"],
                    gender=cast_member["gender"],
                    is_adult=cast_member["is_adult"],
                    tmdb_id=cast_member["tmdb_id"]
                )
                
                # Check Link
                link = self.db.query(MediaPersonLink).filter(
                    MediaPersonLink.match_id == match.id if match.id else False,
                    MediaPersonLink.person_id == person.id if person.id else False,
                    MediaPersonLink.role == RoleType.ACTOR
                ).first()
                if not link:
                    link = MediaPersonLink(
                        role=RoleType.ACTOR,
                        character_name=cast_member["character"],
                        order=idx
                    )
                    link.person = person
                    match.people.append(link)

            self.db.flush()
            return match
