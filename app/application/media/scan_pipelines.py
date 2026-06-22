import logging
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.shared_kernel.enums import ScanMode
from app.domains.library.models import Library
from app.domains.library.services.scanner.collector import Collector
from app.domains.library.services.scanner.scan_collector import ScanCollector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanThresholdConfig:
    size_key: str
    duration_key: str
    default_size_mb: float
    default_duration_minutes: float


class BaseScanPipeline:
    def __init__(self, mode: ScanMode):
        self.mode = mode

    def threshold_config(self) -> ScanThresholdConfig:
        raise NotImplementedError

    def build_collector_phase(
        self,
        db: Session,
        library: Library,
        *,
        prober,
        categorizer,
        linker,
        min_size_mb: float,
        min_duration_minutes: float,
        progress_callback: Optional[Callable],
        provider: Optional[str] = None,
    ) -> ScanCollector:
        collector = Collector(min_size_mb)
        return ScanCollector(
            db=db,
            library=library,
            prober=prober,
            collector=collector,
            categorizer=categorizer,
            linker=linker,
            mode=self.mode,
            min_video_duration_minutes=min_duration_minutes,
            progress_callback=progress_callback,
            provider=provider,
        )


class MainstreamScanPipeline(BaseScanPipeline):
    def __init__(self):
        super().__init__(ScanMode.MOVIES_TV)

    def threshold_config(self) -> ScanThresholdConfig:
        return ScanThresholdConfig(
            size_key='min_video_size_mb',
            duration_key='min_video_duration_minutes',
            default_size_mb=50.0,
            default_duration_minutes=12.0,
        )


class ScenesScanPipeline(BaseScanPipeline):
    def __init__(self):
        super().__init__(ScanMode.SCENES)

    def threshold_config(self) -> ScanThresholdConfig:
        return ScanThresholdConfig(
            size_key='adult_min_video_size_mb',
            duration_key='adult_min_video_duration_minutes',
            default_size_mb=1.0,
            default_duration_minutes=1.0,
        )


class PornDbMovieScanPipeline(BaseScanPipeline):
    def __init__(self):
        super().__init__(ScanMode.PORNDB_MOVIE)

    def threshold_config(self) -> ScanThresholdConfig:
        return ScanThresholdConfig(
            size_key='adult_min_video_size_mb',
            duration_key='adult_min_video_duration_minutes',
            default_size_mb=1.0,
            default_duration_minutes=0.1,
        )


def get_scan_pipeline(mode: ScanMode) -> BaseScanPipeline:
    if mode == ScanMode.SCENES:
        return ScenesScanPipeline()
    if mode == ScanMode.PORNDB_MOVIE:
        return PornDbMovieScanPipeline()
    return MainstreamScanPipeline()
