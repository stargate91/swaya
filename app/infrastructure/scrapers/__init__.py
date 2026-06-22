from typing import Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType
from app.infrastructure.cache.cache_service import CacheService
from app.infrastructure.scrapers.providers.tmdb import TMDBScraper
from app.infrastructure.scrapers.providers.omdb import OMDBScraper
from app.infrastructure.scrapers.providers.stashdb import StashDBScraper
from app.infrastructure.scrapers.providers.porndb import PornDBScraper
from app.infrastructure.scrapers.providers.fansdb import FansDBScraper


class ScraperService:
    """
    Unified facade service that delegates scraper operations to specialized
    sub-scraper classes (TMDB, OMDB, StashDB, PornDB, FansDB) to maintain domain separation.
    """

    def __init__(self, db_session: Session, cache_service: Optional[CacheService] = None):
        self.db = db_session
        self.cache = cache_service or CacheService()
        self.tmdb = TMDBScraper(db_session, self.cache)
        self.omdb = OMDBScraper(db_session, self.cache)
        self.stashdb = StashDBScraper(db_session, self.cache)
        self.porndb = PornDBScraper(db_session, self.cache)
        self.fansdb = FansDBScraper(db_session, self.cache)

    def fetch_tmdb_movie(self, movie_id: str, language: Optional[str] = None, force_refresh: bool = False) -> Optional[dict]:
        return self.tmdb.fetch_movie(movie_id, language, force_refresh)

    def fetch_tmdb_tv(self, tv_id: str, language: Optional[str] = None, force_refresh: bool = False) -> Optional[dict]:
        return self.tmdb.fetch_tv(tv_id, language, force_refresh)

    def fetch_omdb(self, imdb_id: str, force_refresh: bool = False) -> Optional[dict]:
        return self.omdb.fetch_omdb(imdb_id, force_refresh)

    def fetch_stashdb_scene(self, scene_id: str, force_refresh: bool = False) -> Optional[dict]:
        return self.stashdb.fetch_scene(scene_id, force_refresh)

    def fetch_porndb_scene(self, scene_id: str, force_refresh: bool = False) -> Optional[dict]:
        return self.porndb.fetch_scene(scene_id, force_refresh)

    def fetch_fansdb_scene(self, scene_id: str, force_refresh: bool = False) -> Optional[dict]:
        return self.fansdb.fetch_scene(scene_id, force_refresh)
