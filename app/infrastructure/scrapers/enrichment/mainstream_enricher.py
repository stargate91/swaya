import logging
import os
import re
from urllib.parse import urlparse
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization, Studio, MediaCollection
from app.shared_kernel.enums import Provider, MediaType, RoleType
from app.domains.people.models import MediaPersonLink
from app.infrastructure.scrapers.providers.tmdb import TMDBScraper
from app.infrastructure.scrapers.providers.omdb import OMDBScraper
from app.shared_kernel.language import LanguageService
from app.shared_kernel.ports.metadata_repository_port import MetadataRepositoryPort
from app.shared_kernel.ports.people_repository_port import PeopleRepositoryPort
from app.shared_kernel.ports.settings_port import SettingsPort
from app.shared_kernel.ports.image_download_port import ImageDownloadPort

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.infrastructure.scrapers.enrichment.tmdb_parser import TMDBEnrichmentParser
from app.infrastructure.scrapers.enrichment.omdb_parser import OMDBEnrichmentParser

logger = logging.getLogger(__name__)

class MainstreamEnricher:
    """
    Mainstream enricher that queries TMDB/OMDB and populates full localization,
    studios, collection details, and links cast/crew.
    """

    def __init__(
        self,
        db_session: Session,
        metadata_repo: Optional[MetadataRepositoryPort] = None,
        people_repo: Optional[PeopleRepositoryPort] = None,
        settings_port: Optional[SettingsPort] = None,
        image_downloader: Optional[ImageDownloadPort] = None,
    ):
        self.db = db_session
        from app.infrastructure.repositories.db_metadata_repository import DbMetadataRepository
        from app.infrastructure.repositories.db_people_repository import DbPeopleRepository
        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
        from app.infrastructure.tasks.tasks_image_download_adapter import TasksImageDownloadAdapter
        self.metadata_repo = metadata_repo or DbMetadataRepository(db_session)
        self.people_repo = people_repo or DbPeopleRepository(db_session)
        self.settings_port = settings_port or DbSettingsAdapter(db_session)
        self.image_downloader = image_downloader or TasksImageDownloadAdapter()

        self.api = TMDBScraper(db_session)
        self.omdb = OMDBScraper(db_session)
        self._details_cache: Dict[tuple[str, int, str], Dict[str, Any]] = {}
        self._episode_cache: Dict[tuple[int, int, int, str], Dict[str, Any]] = {}
        self._omdb_cache: Dict[str, Dict[str, Any]] = {}

        self.tmdb_parser = TMDBEnrichmentParser(self)
        self.omdb_parser = OMDBEnrichmentParser(self)

    def enrich_matched_item(
        self,
        item: MediaItem,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: str = None,
        include_ratings: bool = True,
        commit: bool = False,
    ):
        """Fetches and stores complete metadata for the active match."""
        active_match = self.metadata_repo.get_match_by_item(item.id, active_only=True)

        if not active_match:
            active_match = self.metadata_repo.get_match_by_item(item.id, active_only=False)

        if not active_match:
            return

        # Build unique list of languages to enrich
        langs_to_enrich = []
        if language:
            langs_to_enrich.append(language)
        if fallback_language:
            langs_to_enrich.append(fallback_language)

        # Retrieve target language and overrides so they are also cached in the DB
        try:
            from app.shared_kernel.user_context import get_current_user_id
            current_user_id = get_current_user_id()
            
            follow_naming = self.settings_port.get_setting("follow_app_language_for_naming", current_user_id)
            if follow_naming is None:
                follow_naming = True
            
            t_lang = None
            if follow_naming:
                t_lang = self.settings_port.get_setting("ui_language", current_user_id)
            else:
                t_lang = self.settings_port.get_setting("default_target_language", current_user_id)
            
            if t_lang:
                langs_to_enrich.append(t_lang)
        except Exception as lang_ex:
            logger.warning(f"Failed to load target language for enrichment: {lang_ex}")

        unique_langs = []
        for raw_language in langs_to_enrich:
            language = LanguageService.resolve_request_locale(Provider.TMDB, raw_language)
            if language and language not in unique_langs:
                unique_langs.append(language)

        for idx, lang in enumerate(unique_langs):
            inc_rat = include_ratings if idx == 0 else False
            if active_match.media_type == MediaType.MOVIE:
                self.tmdb_parser.enrich_movie(active_match, lang, include_ratings=inc_rat)
            elif active_match.media_type == MediaType.TV or active_match.media_type == MediaType.EPISODE:
                self.tmdb_parser.enrich_tv(active_match, lang, include_ratings=inc_rat)

        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def _queue_image(self, path: Optional[str], subfolder: str, prefix: str) -> Optional[str]:
        if not path:
            return None

        url = self.image_downloader.get_download_url(path, subfolder)
        if not url:
            return None

        basename = os.path.basename(urlparse(path).path)
        if not basename:
            return None

        ext = os.path.splitext(basename)[1].lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'}:
            try:
                import requests
                resp = requests.head(url, timeout=3, allow_redirects=True)
                ct = resp.headers.get("Content-Type", "").lower()
                if "png" in ct:
                    ext = ".png"
                elif "webp" in ct:
                    ext = ".webp"
                elif "gif" in ct:
                    ext = ".gif"
                elif "svg" in ct:
                    ext = ".svg"
                else:
                    ext = ".jpg"
            except Exception:
                ext = ".jpg"
            basename = f"{basename}{ext}"

        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
        filename = f"{safe_prefix}_{basename}"
        self.image_downloader.enqueue_download(url, subfolder, filename)
        return f"{subfolder}/{filename}"

    def _get_details_cached(self, tmdb_id: int, item_type: str, language: str) -> Dict[str, Any]:
        cache_key = (item_type, tmdb_id, language)
        if cache_key not in self._details_cache:
            try:
                self._details_cache[cache_key] = self.api.get_details(tmdb_id, item_type=item_type, language=language) or {}
            except Exception as e:
                logger.error(f"Failed to fetch details for {item_type} {tmdb_id}: {e}")
                self._details_cache[cache_key] = {}
        return self._details_cache[cache_key]

    def _get_episode_details_cached(self, tv_id: int, season_number: int, episode_number: int, language: str) -> Dict[str, Any]:
        cache_key = (tv_id, season_number, episode_number, language)
        if cache_key not in self._episode_cache:
            try:
                self._episode_cache[cache_key] = self.api.get_episode_details(
                    tv_id,
                    season_number,
                    episode_number,
                    language=language,
                ) or {}
            except Exception as e:
                logger.error(f"Failed to fetch episode details for TV {tv_id} S{season_number}E{episode_number}: {e}")
                self._episode_cache[cache_key] = {}
        return self._episode_cache[cache_key]

    def _get_omdb_ratings_cached(self, imdb_id: str) -> Dict[str, Any]:
        if imdb_id not in self._omdb_cache:
            self._omdb_cache[imdb_id] = self.omdb.fetch_omdb(imdb_id) or {}
        return self._omdb_cache[imdb_id]
