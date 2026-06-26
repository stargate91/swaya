import difflib
import logging
from typing import Set
from app.shared_kernel.enums import ItemStatus
from app.domains.library.models import MediaItem
from app.infrastructure.scrapers.resolver import normalize_title, normalize_title_words

logger = logging.getLogger(__name__)

def validate_hash_match(item: MediaItem, candidate: dict, current_status: ItemStatus) -> ItemStatus:
    if current_status != ItemStatus.MATCHED:
        return current_status

    parsed = item.parsed_info or {}
    parsed_titles = []
    for key in ["fn", "fd", "it"]:
        data = parsed.get(key) or {}
        parsed_titles.extend([
            data.get("alternative_title"),
            data.get("episode_title"),
            data.get("title")
        ])
    parsed_titles = [t for t in parsed_titles if t]
    if not parsed_titles:
        return current_status

    cand_title = candidate.get("title") or ""
    norm_cand = normalize_title(cand_title)
    cand_words_str = normalize_title_words(cand_title)
    cand_words = set(w for w in cand_words_str.split() if len(w) > 3)
    best_ratio = 0.0
    for t in parsed_titles:
        norm_t = normalize_title(t)
        if not norm_cand or not norm_t:
            continue

        # Substring match (e.g. "Hunger" inside "Valentina Nappi - Hunger")
        if norm_cand in norm_t or norm_t in norm_cand:
            return current_status

        # Word intersection check for words of length > 3
        t_words_str = normalize_title_words(t)
        t_words = set(w for w in t_words_str.split() if len(w) > 3)
        if cand_words & t_words:
            best_ratio = max(best_ratio, 0.6)

        ratio = difflib.SequenceMatcher(None, norm_cand, norm_t).ratio()
        if ratio > best_ratio:
            best_ratio = ratio

    if best_ratio < 0.5:
        norm_filename = normalize_title(item.filename)
        if norm_cand and norm_cand in norm_filename:
            return current_status

        logger.warning(
            'Hash match title similarity validation failed (best ratio %.2f < 0.5) for %s -> %s. Downgrading to UNCERTAIN.',
            best_ratio, item.filename, cand_title
        )
        return ItemStatus.UNCERTAIN

    return current_status
