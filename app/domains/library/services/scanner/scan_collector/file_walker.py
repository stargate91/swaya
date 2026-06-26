import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.shared_kernel.enums import ExtraCategory, ExtraSubtype, ScanMode, Provider
from app.domains.library.models import Library, MediaItem, ExtraFile
from app.domains.library.services.scanner.categorizer import Categorizer

FORCED_EXTRA_VIDEO_SUBTYPES = {
    ExtraSubtype.SAMPLE,
    ExtraSubtype.TRAILER,
    ExtraSubtype.FEATURETTE,
    ExtraSubtype.BEHIND_THE_SCENES,
    ExtraSubtype.DELETED_SCENES,
    ExtraSubtype.INTERVIEW,
    ExtraSubtype.SCENE_COMPARISON,
    ExtraSubtype.SHORT,
    ExtraSubtype.PROMO,
    ExtraSubtype.CLIP,
}

SCENE_FORCE_EXTRA_VIDEO_SUBTYPES = {
    ExtraSubtype.SAMPLE,
    ExtraSubtype.TRAILER,
}

class FileWalker:
    """
    Submodule to manage file classifications, path conversions, duration thresholds, and categorizations.
    """
    def __init__(
        self,
        library: Library,
        categorizer: Categorizer,
        mode: ScanMode = ScanMode.MOVIES_TV,
        min_video_duration_minutes: float = 10,
        provider: Optional[str] = None
    ):
        self.library = library
        self.categorizer = categorizer
        self.mode = mode
        self.min_video_duration_minutes = min_video_duration_minutes
        self.provider = str(provider or "").strip().lower()

    def get_rel_path(self, p: Path) -> str:
        try:
            return os.path.relpath(str(p), self.library.root_path).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")

    def duration_limit_seconds(self, db: Session) -> float:
        provider_duration_overrides = {
            Provider.FANSDB.value: "fansdb_adult_min_video_duration_minutes",
        }
        default_minutes = max(0.0, float(self.min_video_duration_minutes or 0))

        if not self.provider or self.mode != ScanMode.SCENES:
            return default_minutes * 60

        setting_key = provider_duration_overrides.get(self.provider)
        if not setting_key:
            return default_minutes * 60

        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter

        settings = DbSettingsAdapter(db)
        try:
            override_minutes = float(settings.get_setting(setting_key) or default_minutes)
        except (TypeError, ValueError):
            override_minutes = default_minutes
        return max(0.0, override_minutes) * 60

    def should_force_video_to_extra(self, path: Path, db: Session) -> bool:
        category, subtype = self.categorizer.categorize(path, db)
        forced_subtypes = SCENE_FORCE_EXTRA_VIDEO_SUBTYPES if self.mode == ScanMode.SCENES else FORCED_EXTRA_VIDEO_SUBTYPES
        if category == ExtraCategory.VIDEO and subtype in forced_subtypes:
            return True

        joined_parts = " ".join(part.lower() for part in path.parts)
        force_extra_pattern = r"\b(sample|samples|extra|extras|trailer|trailers)\b" if self.mode == ScanMode.SCENES else r"\b(sample|samples|extra|extras|trailer|trailers|bonus|featurette|promo|clip)\b"
        if re.search(force_extra_pattern, joined_parts):
            return True

        return False

    def classify_paths(
        self,
        potential_media: List[Path],
        potential_extras: List[Path],
        probe_durations: Dict[str, Optional[float]],
        probe_infos: Dict[str, Dict[str, Any]],
        db: Session
    ) -> Tuple[List[Path], List[Path]]:
        """
        Classifies collected files into media paths and extra paths based on duration and forced subtypes.
        """
        media_paths = []
        extra_paths = list(potential_extras)
        limit_seconds = self.duration_limit_seconds(db)

        for p in potential_media:
            p_str = str(p)
            duration = probe_durations.get(p_str)
            res = probe_infos.get(p_str)
            info = res.get("probe_info") if res else None
            is_audio_only = False
            if info:
                has_video = bool(info.get("video_codec"))
                has_audio = len(info.get("audio_streams") or []) > 0
                if not has_video and has_audio:
                    is_audio_only = True

            forced_extra = self.should_force_video_to_extra(p, db)
            if forced_extra or is_audio_only or (duration is not None and duration < limit_seconds):
                extra_paths.append(p)
            else:
                media_paths.append(p)

        return media_paths, extra_paths
