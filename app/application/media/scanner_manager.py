import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.core.enums import ScanMode

from app.domains.media.models.filesystem import Library, MediaItem
from app.domains.settings.models import SystemSetting, UserSetting
from app.domains.media.services.scanner.collector import Collector
from app.domains.media.services.scanner.categorizer import Categorizer
from app.domains.media.services.scanner.linker import Linker
from app.domains.media.services.scanner.probe import TechnicalProber
from app.domains.media.services.scanner.scan_collector import ScanCollector

logger = logging.getLogger(__name__)

class ScannerManager:
    """
    Coordinator/Facade for the library scanning pipeline.
    Executes scanning stages (collection, technical probing, and link establishment).
    """

    def __init__(self, db_session: Session, min_video_size_mb: float = 50, min_video_duration_minutes: float = 12):
        self.db = db_session
        self.default_min_video_size_mb = min_video_size_mb
        self.default_min_video_duration_minutes = min_video_duration_minutes
        self.categorizer = Categorizer()
        self.linker = Linker()
        self.prober = TechnicalProber()

    def _get_numeric_setting(self, key: str, default: float) -> float:
        setting = self.db.query(UserSetting).filter(
            UserSetting.user_id == 1,
            UserSetting.key == key,
        ).first()
        if not setting:
            setting = self.db.query(SystemSetting).filter(SystemSetting.key == key).first()

        try:
            return max(0.0, float(setting.value)) if setting and setting.value is not None else default
        except (TypeError, ValueError):
            logger.warning(f"Invalid scanner threshold for {key}; using default {default}.")
            return default

    def scan_library(
        self,
        library_id: int,
        mode: ScanMode = ScanMode.MOVIES_TV,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[List[MediaItem], Dict[str, Any]]:
        """
        Runs Phase 1 scanning on a specific Library.
        Collects files, probes technical details, links extras, and saves items.
        """
        library = self.db.query(Library).filter(Library.id == library_id).first()
        if not library:
            logger.error(f"Library {library_id} not found in database.")
            return [], {}

        logger.info(f"Starting scan for source root: {library.name} (Root: {library.root_path}, Mode: {mode.value})")
        
        if mode.uses_scene_pipeline:
            size_key = "adult_min_video_size_mb"
            dur_key = "adult_min_video_duration_minutes"
            default_size = 1.0
            default_dur = 0.1
        else:
            size_key = "min_video_size_mb"
            dur_key = "min_video_duration_minutes"
            default_size = float(self.default_min_video_size_mb)
            default_dur = float(self.default_min_video_duration_minutes)

        min_size_mb = self._get_numeric_setting(size_key, default_size)
        min_duration_mins = self._get_numeric_setting(dur_key, default_dur)

        logger.info(f"Scan settings ({mode.value}) - min_size_mb: {min_size_mb}, min_duration_mins: {min_duration_mins}")

        collector = Collector(min_size_mb)
        collector_phase = ScanCollector(
            db=self.db,
            library=library,
            prober=self.prober,
            collector=collector,
            categorizer=self.categorizer,
            linker=self.linker,
            mode=mode,
            min_video_duration_minutes=min_duration_mins,
            progress_callback=progress_callback
        )
        
        try:
            to_process, probe_infos = collector_phase.collect_and_save()
            logger.info(f"Library scan complete. Found {len(to_process)} new/modified items needing enrichment.")
            return to_process, probe_infos
        except Exception as e:
            logger.error(f"Library scan failed: {e}", exc_info=True)
            raise

