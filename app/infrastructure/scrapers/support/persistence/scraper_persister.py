import logging
import threading
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.metadata.models import MetadataMatch, Studio
from app.shared_kernel.ports.metadata_repository_port import MetadataRepositoryPort
from app.shared_kernel.ports.people_repository_port import PeopleRepositoryPort
from app.shared_kernel.ports.image_download_port import ImageDownloadPort

from app.infrastructure.scrapers.support.persistence.match_persister import MatchPersister
from app.infrastructure.scrapers.support.persistence.studio_persister import StudioPersister
from app.infrastructure.scrapers.support.persistence.performer_persister import PerformerPersister

logger = logging.getLogger(__name__)

persistence_lock = threading.Lock()

class ScraperPersister:
    """
    Handles database persistence for scraper metadata.
    Decoupled from scraper classes to maintain clean domain boundaries.
    """

    def __init__(
        self,
        db: Session,
        metadata_repo: Optional[MetadataRepositoryPort] = None,
        people_repo: Optional[PeopleRepositoryPort] = None,
        image_downloader: Optional[ImageDownloadPort] = None,
    ):
        self.db = db
        from app.infrastructure.repositories.db_metadata_repository import DbMetadataRepository
        from app.infrastructure.repositories.db_people_repository import DbPeopleRepository
        from app.infrastructure.tasks.tasks_image_download_adapter import TasksImageDownloadAdapter
        self.metadata_repo = metadata_repo or DbMetadataRepository(db)
        self.people_repo = people_repo or DbPeopleRepository(db)
        self.image_downloader = image_downloader or TasksImageDownloadAdapter()

        self.match_persister = MatchPersister(self)
        self.studio_persister = StudioPersister(self)
        self.performer_persister = PerformerPersister(self)

    def persist_normalized_scene(
        self,
        provider: Provider,
        scene_id: str,
        norm: Dict[str, Any],
        media_type: MediaType = MediaType.SCENE,
        media_item_id: Optional[int] = None,
    ) -> MetadataMatch:
        """Takes a normalized scene structure and persists it to the database."""
        with persistence_lock:
            match = self.metadata_repo.get_match(
                provider=provider,
                external_id=scene_id,
                media_type=media_type,
                media_item_id=media_item_id
            )

            if not match:
                try:
                    with self.db.begin_nested():
                        match = self.metadata_repo.create_match(
                            provider=provider,
                            external_id=scene_id,
                            media_type=media_type,
                            media_item_id=media_item_id
                        )
                        self.metadata_repo.flush()
                except Exception:
                    match = self.metadata_repo.get_match(
                        provider=provider,
                        external_id=scene_id,
                        media_type=media_type,
                        media_item_id=media_item_id
                    )

            for k, v in norm["match"].items():
                setattr(match, k, v)

            self.studio_persister.persist_studios(norm.get("studios", []), match)

            loc = None
            for l in match.localizations:
                if l.locale == DEFAULT_FALLBACK_LANGUAGE:
                    loc = l
                    break
            if not loc:
                loc = self.metadata_repo.get_localization(match.id, DEFAULT_FALLBACK_LANGUAGE)
            if not loc:
                loc = self.metadata_repo.create_localization(match.id, DEFAULT_FALLBACK_LANGUAGE)
                for k, v in norm["localization"].items():
                    if k != "genres":
                        setattr(loc, k, v)
                if loc not in match.localizations:
                    match.localizations.append(loc)
                try:
                    with self.db.begin_nested():
                        self.metadata_repo.flush()
                except Exception:
                    loc = self.metadata_repo.get_localization(match.id, DEFAULT_FALLBACK_LANGUAGE)
            else:
                for k, v in norm["localization"].items():
                    if k != "genres":
                        setattr(loc, k, v)

            self.performer_persister.persist_performers(norm.get("performers", []), match, limit_cast=0)

            self.metadata_repo.flush()
            self.match_persister.queue_adult_assets(match)
            return match

    def persist_normalized_movie(self, movie_id: str, norm: Dict[str, Any], language: str) -> MetadataMatch:
        """Takes a normalized movie structure and persists it to the database."""
        with persistence_lock:
            match = self.metadata_repo.get_match(
                provider=Provider.TMDB,
                external_id=movie_id,
                media_type=MediaType.MOVIE
            )

            if not match:
                try:
                    with self.db.begin_nested():
                        match = self.metadata_repo.create_match(
                            provider=Provider.TMDB,
                            external_id=movie_id,
                            media_type=MediaType.MOVIE
                        )
                        self.metadata_repo.flush()
                except Exception:
                    match = self.metadata_repo.get_match(
                        provider=Provider.TMDB,
                        external_id=movie_id,
                        media_type=MediaType.MOVIE
                    )

            for k, v in norm["match"].items():
                setattr(match, k, v)

            self.studio_persister.persist_studios(norm.get("studios", []), match)

            coll_info = norm.get("collection")
            if coll_info:
                self.match_persister.persist_collection(coll_info, match, language)

            loc = None
            for l in match.localizations:
                if l.locale == language:
                    loc = l
                    break
            if not loc:
                loc = self.metadata_repo.get_localization(match.id, language)
            if not loc:
                loc = self.metadata_repo.create_localization(match.id, language)
                for k, v in norm["localization"].items():
                    setattr(loc, k, v)
                if loc not in match.localizations:
                    match.localizations.append(loc)
                try:
                    with self.db.begin_nested():
                        self.metadata_repo.flush()
                except Exception:
                    loc = self.metadata_repo.get_localization(match.id, language)
            else:
                for k, v in norm["localization"].items():
                    setattr(loc, k, v)

            self.performer_persister.persist_performers(norm.get("performers", []), match, limit_cast=15)

            self.metadata_repo.flush()
            self.match_persister.queue_adult_assets(match)
            return match

    def _queue_studio_logo(self, studio: Studio) -> None:
        self.studio_persister.queue_studio_logo(studio)
