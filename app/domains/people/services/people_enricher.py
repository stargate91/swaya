import logging
from typing import List, Optional, Callable, Any
import requests
from sqlalchemy.orm import Session
from app.domains.people.models import Person
from app.shared_kernel.ports.scrapers import ScraperGatewayPort

from app.shared_kernel.ports.task_monitor_port import TaskMonitorPort
from app.domains.people.services.enrichment.mainstream import TMDBEnricher
from app.domains.people.services.enrichment.adult import AdultEnricher

from app.domains.people.services.enrichment.task import enrich_people_for_matches
from app.domains.people.services.enrichment.fetcher import fetch_external_details
from app.domains.people.services.enrichment.persister import apply_enriched_data

logger = logging.getLogger(__name__)

class PeopleEnricher:
    def __init__(
        self,
        db: Optional[Session],
        scrapers: Optional[ScraperGatewayPort] = None,
        session_factory: Optional[Callable[[], Session]] = None,
        is_cancelled: Optional[Callable[[int], bool]] = None,
        has_active_heavy_tasks: Optional[Callable[[], bool]] = None,
        executor: Optional[Any] = None,
        update_progress: Optional[Callable[[int, float], None]] = None,
        task_monitor: Optional[TaskMonitorPort] = None,
        image_downloader: Optional[Any] = None,
    ):
        self.db = db
        self.scrapers = scrapers
        self.session_factory = session_factory
        self._is_cancelled_cb = is_cancelled
        self._has_active_heavy_tasks_cb = has_active_heavy_tasks
        self._executor = executor
        self._update_progress_cb = update_progress
        self.task_monitor = task_monitor
        self.image_downloader = image_downloader
        self.session = requests.Session()
        self.tmdb_enricher = TMDBEnricher(self.scrapers, self._get_temp_db, self._close_temp_db) if self.scrapers else None
        self.adult_enricher = AdultEnricher(self.scrapers, self._get_temp_db, self._close_temp_db) if self.scrapers else None

    def _close_temp_db(self, session: Session) -> None:
        if self.session_factory:
            session.close()

    def _is_cancelled(self, task_id: int) -> bool:
        if self._is_cancelled_cb:
            return self._is_cancelled_cb(task_id)
        if self.task_monitor:
            return self.task_monitor.is_cancelled(task_id)
        return False

    def _has_active_heavy_tasks(self) -> bool:
        if self._has_active_heavy_tasks_cb:
            return self._has_active_heavy_tasks_cb()
        if self.task_monitor:
            return self.task_monitor.has_active_heavy_tasks()
        return False

    def _get_executor(self):
        if self._executor:
            return self._executor
        if self.task_monitor:
            return self.task_monitor.executor
        import concurrent.futures
        return concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def _update_progress(self, task_id: int, progress: float) -> None:
        if self._update_progress_cb:
            self._update_progress_cb(task_id, progress)
        elif self.task_monitor:
            self.task_monitor.update_progress(task_id, progress)

    def _require_scrapers(self) -> ScraperGatewayPort:
        if self.scrapers is None:
            raise RuntimeError("Scraper gateway is required for people enrichment")
        return self.scrapers

    def _get_temp_db(self) -> Session:
        if self.session_factory:
            return self.session_factory()
        if self.db:
            return self.db
        raise RuntimeError("PeopleEnricher requires session_factory or db to be provided")

    def enrich_people_for_matches(self, task_id: int, match_ids: List[int], progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        return enrich_people_for_matches(self, task_id, match_ids, progress_callback)

    def fetch_external_details(self, name: str, external_ids: dict, links: List[dict], settings: Optional[dict] = None, is_adult: bool = False) -> Optional[dict]:
        return fetch_external_details(self, name, external_ids, links, settings, is_adult)

    def apply_enriched_data(self, person: Person, data: dict):
        return apply_enriched_data(self, person, data)

