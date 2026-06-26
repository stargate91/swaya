from typing import Tuple, Optional, Any
from pathlib import Path
from sqlalchemy.orm import Session
from app.shared_kernel.enums import ScanMode, ExtraCategory, ExtraSubtype

class ExtraDeterminer:
    def __init__(self, categorizer: Any, mode: ScanMode):
        self.categorizer = categorizer
        self.mode = mode

    def determine_extra(self, path: Path, db: Session) -> Tuple[Optional[ExtraCategory], Optional[ExtraSubtype]]:
        category, subtype = self.categorizer.categorize(path, db)
        if category is None:
            return None, None

        # Scene profiles support sidecar metadata, images, subtitles, and audio tracks.
        if self.mode == ScanMode.SCENES and category not in (
            ExtraCategory.METADATA,
            ExtraCategory.IMAGE,
            ExtraCategory.SUBTITLE,
            ExtraCategory.AUDIO,
        ):
            return None, None

        return category, subtype
