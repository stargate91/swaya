from pathlib import Path
from typing import Tuple, Optional
from app.shared_kernel.enums import ExtraCategory, ExtraSubtype
from app.shared_kernel.ports.settings_port import SettingsPort
from app.shared_kernel.constants import (
    SCANNER_SUBTYPE_MAP,
    CATEGORIZER_VIDEO_EXTS,
    CATEGORIZER_SUBTITLE_EXTS,
    CATEGORIZER_IMAGE_EXTS,
    CATEGORIZER_AUDIO_EXTS,
    CATEGORIZER_META_EXTS,
)

class Categorizer:
    """
    Submodule: Categorizes extra files (subtitles, images, etc.) 
    into logical categories and subtypes based on filename keywords and extensions.
    """
    
    # Keyword mapping for automated subtype detection
    SUBTYPE_MAP = SCANNER_SUBTYPE_MAP

    def categorize(self, file_path: Path, db_session=None, settings_port: Optional[SettingsPort] = None) -> Tuple[Optional[ExtraCategory], Optional[ExtraSubtype]]:
        """
        Determines the category and subtype of a file.
        Uses extensions for primary categorization and keywords for subtype refinement.
        """
        ext = file_path.suffix.lower()
        filename = file_path.stem.lower()
        
        # Default extensions list
        sub_exts = list(CATEGORIZER_SUBTITLE_EXTS)
        audio_exts = list(CATEGORIZER_AUDIO_EXTS)
        img_exts = list(CATEGORIZER_IMAGE_EXTS)
        meta_exts = list(CATEGORIZER_META_EXTS)
        video_exts = list(CATEGORIZER_VIDEO_EXTS)
        
        settings = None
        if settings_port:
            try:
                settings = settings_port.get_all_system_settings()
            except Exception:
                pass
        elif db_session:
            try:
                from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
                settings = DbSettingsAdapter(db_session).get_all_system_settings()
            except Exception:
                pass

        if settings:
            if "extras_sub_exts" in settings: sub_exts = [e.strip() for e in settings["extras_sub_exts"].split(",")]
            if "extras_audio_exts" in settings: audio_exts = [e.strip() for e in settings["extras_audio_exts"].split(",")]
            if "extras_img_exts" in settings: img_exts = [e.strip() for e in settings["extras_img_exts"].split(",")]
            if "extras_meta_exts" in settings: meta_exts = [e.strip() for e in settings["extras_meta_exts"].split(",")]
            if "naming_video_exts" in settings:
                video_exts = [
                    e.strip().lower() if e.strip().startswith('.') else f".{e.strip().lower()}"
                    for e in settings["naming_video_exts"].split(",") if e.strip()
                ]

        # Primary categorization based on extensions
        category = None
        
        if ext in sub_exts:
            category = ExtraCategory.SUBTITLE
        elif ext in audio_exts:
            category = ExtraCategory.AUDIO
        elif ext in img_exts:
            category = ExtraCategory.IMAGE
        elif ext in meta_exts:
            category = ExtraCategory.METADATA
        elif ext in video_exts:
             category = ExtraCategory.VIDEO
             
        # Refine subtype based on keywords
        subtype = None
        for keyword, mapped_subtype in self.SUBTYPE_MAP.items():
            if keyword in filename:
                subtype = mapped_subtype
                break
            
        # Guard: DUBBED is audio-only
        if category == ExtraCategory.SUBTITLE and subtype == ExtraSubtype.DUBBED:
            subtype = None
            
        # Context-aware Commentary assignment
        if subtype == ExtraSubtype.COMMENTARY_SUB:
            if category == ExtraCategory.AUDIO:
                subtype = ExtraSubtype.COMMENTARY_AUDIO
            elif category == ExtraCategory.VIDEO:
                subtype = ExtraSubtype.FEATURETTE

        # Special case for Metadata files
        if ext == '.nfo': subtype = ExtraSubtype.NFO
        elif ext == '.xml': subtype = ExtraSubtype.XML
        elif ext == '.json': subtype = ExtraSubtype.JSON
        elif ext == '.txt': subtype = ExtraSubtype.TXT
                
        return category, subtype

