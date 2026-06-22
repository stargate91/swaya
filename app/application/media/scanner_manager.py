import logging
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.shared_kernel.enums import ScanMode

from app.domains.library.models import Library, MediaItem
from app.domains.settings.models import SystemSetting, UserSetting
from app.domains.library.services.scanner.categorizer import Categorizer
from app.domains.library.services.scanner.linker import Linker
from app.domains.library.services.scanner.probe import TechnicalProber
from app.application.media.scan_pipelines import get_scan_pipeline

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
        from app.shared_kernel.user_context import get_current_user_id
        current_user_id = get_current_user_id()
        setting = self.db.query(UserSetting).filter(
            UserSetting.user_id == current_user_id,
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

        pipeline = get_scan_pipeline(mode)
        thresholds = pipeline.threshold_config()
        min_size_mb = self._get_numeric_setting(thresholds.size_key, thresholds.default_size_mb)
        min_duration_mins = self._get_numeric_setting(thresholds.duration_key, thresholds.default_duration_minutes)

        logger.info(f"Scan settings ({mode.value}) - min_size_mb: {min_size_mb}, min_duration_mins: {min_duration_mins}")

        collector_phase = pipeline.build_collector_phase(
            self.db,
            library,
            prober=self.prober,
            categorizer=self.categorizer,
            linker=self.linker,
            min_size_mb=min_size_mb,
            min_duration_minutes=min_duration_mins,
            progress_callback=progress_callback,
        )
        
        try:
            to_process, probe_infos = collector_phase.collect_and_save()
            logger.info(f"Library scan complete. Found {len(to_process)} new/modified items needing enrichment.")
            return to_process, probe_infos
        except Exception as e:
            logger.error(f"Library scan failed: {e}", exc_info=True)
            raise

