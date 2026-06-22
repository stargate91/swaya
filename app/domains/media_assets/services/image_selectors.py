import os
import logging
from pathlib import Path
from typing import Optional
from PIL import Image
from io import BytesIO
import requests
from app.shared_kernel.constants import (
    TMDB_IMAGE_BASE,
    DEFAULT_FALLBACK_LANGUAGE,
    LOGO_MAX_DARK_PIXELS_RATIO,
    LOGO_MIN_LUMINANCE_RATIO,
    BACKDROP_BRIGHTNESS_THRESHOLD,
    BACKDROP_MAX_BRIGHT_PIXELS_RATIO,
    BACKDROP_4K_WIDTH,
    BACKDROP_ULTRA_HD_WIDTH,
    BACKDROP_DEFAULT_MIN_WIDTH,
    IMAGE_DOWNLOAD_TIMEOUT,
)

def measure_logo_darkness(image: Image.Image) -> Optional[tuple[float, float]]:
    rgba = image.convert("RGBA")
    rgba.thumbnail((256, 256))
    dark_pixels = 0.0
    weighted_luminance = 0.0
    total_alpha = 0.0
    for red, green, blue, alpha in rgba.getdata():
        if alpha <= 0:
            continue
        alpha_weight = alpha / 255.0
        luminance = ((0.2126 * red) + (0.7152 * green) + (0.0722 * blue)) / 255.0
        if luminance < 0.22:
            dark_pixels += alpha_weight
        weighted_luminance += luminance * alpha_weight
        total_alpha += alpha_weight
    if total_alpha <= 0:
        return None
    return (dark_pixels / total_alpha, weighted_luminance / total_alpha)


def probe_logo_darkness(file_path: str, image_root: Path, session: requests.Session) -> Optional[tuple[float, float]]:
    suffix = Path(file_path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None

    local_file = image_root / "original" / "logos" / file_path.lstrip("/")
    try:
        if local_file.exists():
            with Image.open(local_file) as image:
                return measure_logo_darkness(image)
    except Exception:
        pass

    try:
        url = f"{TMDB_IMAGE_BASE}original{file_path}"
        response = session.get(url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        with Image.open(BytesIO(response.content)) as image:
            return measure_logo_darkness(image)
    except Exception:
        return None


def pick_logo_path(
    raw_data: dict,
    image_root: Path,
    session: requests.Session,
    preferred_language: Optional[str] = None
) -> Optional[str]:
    """
    Analyzes and selects the best logo from TMDB metadata images.
    Ensures the logo has sufficient luminance to be readable on dark overlays.
    """
    images = (raw_data or {}).get("images") or {}
    logos = images.get("logos") or []
    if not logos:
        return (raw_data or {}).get("logo_path")

    preferred_langs = []
    normalized_preferred = str(preferred_language or "").split("-", 1)[0].strip().lower()
    if normalized_preferred:
        preferred_langs.append(normalized_preferred)
    preferred_langs.extend([DEFAULT_FALLBACK_LANGUAGE, None, ""])

    def base_logo_score(logo):
        lang = logo.get("iso_639_1")
        normalized_lang = lang.lower() if isinstance(lang, str) else lang
        try:
            lang_rank = preferred_langs.index(normalized_lang)
        except ValueError:
            lang_rank = len(preferred_langs)
        width = int(logo.get("width") or 0)
        vote_average = float(logo.get("vote_average") or 0)
        vote_count = int(logo.get("vote_count") or 0)
        file_type = str(logo.get("file_type") or "").lower()
        return (lang_rank, -vote_count, -vote_average, -width, 0 if file_type == ".svg" else 1)

    ranked_logos = sorted(logos, key=base_logo_score)
    best_language_rank = base_logo_score(ranked_logos[0])[0]
    same_language_candidates = [logo for logo in ranked_logos if base_logo_score(logo)[0] == best_language_rank][:6]

    fallback_candidate = None
    fallback_darkness = None
    for logo in same_language_candidates:
        file_path = logo.get("file_path")
        if not file_path:
            continue
        darkness = probe_logo_darkness(file_path, image_root, session)
        if darkness is None:
            if fallback_candidate is None:
                fallback_candidate = logo
            continue
        if darkness[0] <= LOGO_MAX_DARK_PIXELS_RATIO and darkness[1] >= LOGO_MIN_LUMINANCE_RATIO:
            return file_path
        if (
            fallback_candidate is None
            or fallback_darkness is None
            or fallback_darkness[0] > darkness[0]
        ):
            fallback_candidate = logo
            fallback_darkness = darkness

    picked = fallback_candidate or ranked_logos[0]
    return picked.get("file_path")


def measure_backdrop_tone(image: Image.Image) -> Optional[tuple[float, float]]:
    rgb = image.convert("RGB")
    rgb.thumbnail((320, 180))
    bright_pixels = 0
    total_pixels = 0
    luminance_total = 0.0
    for red, green, blue in rgb.getdata():
        luminance = ((0.2126 * red) + (0.7152 * green) + (0.0722 * blue)) / 255.0
        if luminance >= BACKDROP_BRIGHTNESS_THRESHOLD:
            bright_pixels += 1
        luminance_total += luminance
        total_pixels += 1
    if total_pixels <= 0:
        return None
    return (bright_pixels / total_pixels, luminance_total / total_pixels)


def probe_backdrop_tone(file_path: str, image_root: Path, session: requests.Session) -> Optional[tuple[float, float]]:
    suffix = Path(file_path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None

    local_file = image_root / "original" / "backdrops" / file_path.lstrip("/")
    try:
        if local_file.exists():
            with Image.open(local_file) as image:
                return measure_backdrop_tone(image)
    except Exception:
        pass

    try:
        url = f"{TMDB_IMAGE_BASE}original{file_path}"
        response = session.get(url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
        response.raise_for_status()
        with Image.open(BytesIO(response.content)) as image:
            return measure_backdrop_tone(image)
    except Exception:
        return None


def pick_backdrop_path(
    raw_data: dict,
    image_root: Path,
    session: requests.Session,
    preferred_language: Optional[str] = None,
    min_width: int = BACKDROP_DEFAULT_MIN_WIDTH,
    allow_low_res: bool = True
) -> Optional[str]:
    """
    Analyzes and selects the best backdrop from TMDB metadata images.
    Filters out over-bright (white) backdrops to maintain readability of overlaid text.
    """
    raw = raw_data or {}
    backdrops = ((raw.get("images") or {}).get("backdrops") or [])
    main_backdrop_path = raw.get("backdrop_path")

    if not allow_low_res:
        main_is_ok = True
        if main_backdrop_path and backdrops:
            main_is_ok = any(
                bd.get("file_path") == main_backdrop_path and int(bd.get("width") or 0) >= min_width
                for bd in backdrops
            )
        if not main_is_ok:
            main_backdrop_path = None

        backdrops = [bd for bd in backdrops if int(bd.get("width") or 0) >= min_width]

    if not backdrops:
        return main_backdrop_path

    def backdrop_score(backdrop):
        vote_count = int(backdrop.get("vote_count") or 0)
        vote_average = float(backdrop.get("vote_average") or 0)
        width = int(backdrop.get("width") or 0)
        height = int(backdrop.get("height") or 0)
        return (-vote_count, -vote_average, -width, -height)

    ranked_all_backdrops = sorted(backdrops, key=backdrop_score)
    neutral_backdrops = [bd for bd in backdrops if bd.get("iso_639_1") in (None, "")]

    if not neutral_backdrops:
        return ranked_all_backdrops[0].get("file_path") or main_backdrop_path

    ranked_backdrops = sorted(neutral_backdrops, key=backdrop_score)

    # 1. Look for a good neutral backdrop >= BACKDROP_4K_WIDTH (4K)
    fallback_candidate = None
    fallback_tone = None
    for bd in ranked_backdrops:
        file_path = bd.get("file_path")
        width = int(bd.get("width") or 0)
        if not file_path or width < BACKDROP_4K_WIDTH:
            continue
        tone = probe_backdrop_tone(file_path, image_root, session)
        if tone is None:
            return file_path
        if tone[0] <= BACKDROP_MAX_BRIGHT_PIXELS_RATIO:
            return file_path
        if fallback_candidate is None or fallback_tone is None or tone[0] < fallback_tone[0]:
            fallback_candidate = file_path
            fallback_tone = tone

    # 2. Look for a good neutral backdrop in [2K, 4K) range
    for bd in ranked_backdrops:
        file_path = bd.get("file_path")
        width = int(bd.get("width") or 0)
        if not file_path or width < BACKDROP_ULTRA_HD_WIDTH or width >= BACKDROP_4K_WIDTH:
            continue
        tone = probe_backdrop_tone(file_path, image_root, session)
        if tone is None:
            return file_path
        if tone[0] <= BACKDROP_MAX_BRIGHT_PIXELS_RATIO:
            return file_path
        if fallback_candidate is None or fallback_tone is None or tone[0] < fallback_tone[0]:
            fallback_candidate = file_path
            fallback_tone = tone

    # 3. Look for a good one in [min_width, 2K) range
    for bd in ranked_backdrops:
        file_path = bd.get("file_path")
        width = int(bd.get("width") or 0)
        if not file_path or width < min_width or width >= BACKDROP_ULTRA_HD_WIDTH:
            continue
        tone = probe_backdrop_tone(file_path, image_root, session)
        if tone is None:
            return file_path
        if tone[0] <= BACKDROP_MAX_BRIGHT_PIXELS_RATIO:
            return file_path
        if fallback_candidate is None or fallback_tone is None or tone[0] < fallback_tone[0]:
            fallback_candidate = file_path
            fallback_tone = tone

    return (
        fallback_candidate 
        or ranked_all_backdrops[0].get("file_path") 
        or main_backdrop_path 
        or ranked_backdrops[0].get("file_path")
    )
