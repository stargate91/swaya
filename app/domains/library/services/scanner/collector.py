import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from app.shared_kernel.ports.settings_port import SettingsPort
from app.shared_kernel.constants import (
    DEFAULT_VIDEO_EXTS,
    DEFAULT_SUBTITLE_EXTS,
    DEFAULT_IMAGE_EXTS,
    DEFAULT_AUDIO_EXTS,
    DEFAULT_META_EXTS,
)

class Collector:
    """
    Submodule: Discovers and collects all files from specified paths.
    Categorizes them into primary media (Videos) and potential extras (Images, Subtitles, etc.).
    """
    
    # Rest of class
    VIDEO_EXTS = DEFAULT_VIDEO_EXTS
    SUBTITLE_EXTS = DEFAULT_SUBTITLE_EXTS
    IMAGE_EXTS = DEFAULT_IMAGE_EXTS
    AUDIO_EXTS = DEFAULT_AUDIO_EXTS
    META_EXTS = DEFAULT_META_EXTS

    def __init__(self, min_video_size_mb: float = 50.0):
        self.fast_track_size = min_video_size_mb * 1024 * 1024

    def collect(self, paths: List[str], db_session: Session = None, settings_port: Optional[SettingsPort] = None) -> Dict[str, List[Path]]:
        """
        Recursively traverses directories and groups files into categories.
        """
        results = {
            "potential_media": [], # Primary video files exceeding threshold
            "potential_extras": [], # Smaller videos, images, subtitles, etc.
            "ignored": []
        }

        # Load dynamic video extensions from database settings if available
        video_exts = self.VIDEO_EXTS
        setting_val = None
        if settings_port:
            try:
                setting_val = settings_port.get_system_setting("naming_video_exts")
            except Exception:
                pass
        elif db_session:
            try:
                from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
                setting_val = DbSettingsAdapter(db_session).get_system_setting("naming_video_exts")
            except Exception:
                pass

        if setting_val:
            video_exts = {
                e.strip().lower() if e.strip().startswith('.') else f".{e.strip().lower()}"
                for e in str(setting_val).split(",") if e.strip()
            }

        def process_file(file_path: Path):
            # Skip hidden files and directories
            if any(part.startswith('.') for part in file_path.parts):
                results["ignored"].append(file_path)
                return

            ext = file_path.suffix.lower()
            
            # Filter video files by size
            if ext in video_exts:
                try:
                    size = file_path.stat().st_size
                except Exception:
                    size = 0
                if size >= self.fast_track_size:
                    results["potential_media"].append(file_path)
                else:
                    results["potential_extras"].append(file_path)
            
            elif ext in self.SUBTITLE_EXTS or \
                 ext in self.IMAGE_EXTS or \
                 ext in self.AUDIO_EXTS or \
                 ext in self.META_EXTS:
                results["potential_extras"].append(file_path)
            
            else:
                results["ignored"].append(file_path)

        for root_path in paths:
            p = Path(root_path)
            if not p.exists():
                continue
            
            if p.is_file():
                process_file(p)
            else:
                for file_path in p.rglob("*"): # Recursive traversal
                    if file_path.is_file():
                        process_file(file_path)

        return results
