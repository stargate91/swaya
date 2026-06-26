import threading
from typing import Optional
from app.shared_kernel.constants import YOUTUBE_WATCH_BASE, DEFAULT_FALLBACK_LANGUAGE

tv_enrich_lock = threading.Lock()

def _pick_trailer_key(raw_data, language: str = None, original_language: str = None) -> Optional[str]:
    videos = (raw_data.get("videos") or {}).get("results") or []
    if not videos:
        return None
    youtube_videos = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
    if not youtube_videos:
        youtube_videos = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
    if not youtube_videos:
        return None
    lang_pref = [language, DEFAULT_FALLBACK_LANGUAGE, original_language]
    def score(v):
        v_lang = v.get("iso_639_1")
        try:
            lang_idx = lang_pref.index(v_lang)
        except ValueError:
            lang_idx = 999
        return -lang_idx
    sorted_v = sorted(youtube_videos, key=score, reverse=True)
    key = sorted_v[0].get("key")
    return f"{YOUTUBE_WATCH_BASE}{key}" if key else None
