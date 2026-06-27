import math
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from app.domains.media_assets.services.images import image_processing_service

TALK_LIKE_GENRE_IDS = {10763, 10764, 10767}
SELF_ROLE_KEYWORDS = {"self", "himself", "herself", "themselves", "guest", "host", "presenter", "interviewer"}
VOICE_ROLE_KEYWORDS = {"voice", "vo", "dub", "dubbed", "narrator", "announcer"}
DIRECTING_JOBS = {"director", "creator"}
WRITING_JOBS = {"writer", "screenplay", "story", "teleplay"}

def _normalize_words(value: Optional[str]) -> set[str]:
    if not value:
        return set()
    return {
        word.strip(".,:;!?()[]{}\"'").lower()
        for word in str(value).replace("/", " ").replace("-", " ").split()
        if word.strip()
    }

def _is_self_or_guest_credit(credit: dict) -> bool:
    role_words = _normalize_words(credit.get("job"))
    if role_words.intersection(SELF_ROLE_KEYWORDS):
        return True

    if any(word in {"self", "guest"} for word in _normalize_words(credit.get("character"))):
        return True

    genre_ids = set(credit.get("genre_ids") or [])
    if genre_ids.intersection(TALK_LIKE_GENRE_IDS) and not credit.get("character"):
        return True

    return False

def _department_matches_credit(credit: dict, department: Optional[str]) -> bool:
    normalized_department = str(department or "").strip().lower()
    if not normalized_department:
        return False

    job_words = _normalize_words(credit.get("job"))
    media_type = credit.get("media_type")

    if normalized_department == "acting":
        return media_type in {"movie", "tv"} and bool(credit.get("character"))
    if normalized_department in {"directing", "creator"}:
        return bool(job_words.intersection(DIRECTING_JOBS))
    if normalized_department == "writing":
        return bool(job_words.intersection(WRITING_JOBS))

    return False

def _is_voice_credit(credit: dict) -> bool:
    character_words = _normalize_words(credit.get("character"))
    job_words = _normalize_words(credit.get("job"))
    if character_words.intersection(VOICE_ROLE_KEYWORDS):
        return True
    return bool(job_words.intersection(VOICE_ROLE_KEYWORDS))

def known_for_score(credit: dict, department: Optional[str], adult_only: bool = False, person_name: Optional[str] = None) -> float:
    score = 0.0

    vote_average = float(credit.get("rating") or credit.get("vote_average") or 0.0)
    vote_count = float(credit.get("vote_count") or 0.0)
    popularity = float(credit.get("popularity") or 0.0)

    if adult_only and vote_count < 10:
        vote_average = (vote_average * vote_count + 5.0 * (10 - vote_count)) / 10.0

    vote_count_weight = 10.0

    score += vote_average * 6.0
    score += math.log1p(max(vote_count, 0.0)) * vote_count_weight
    score += min(popularity, 1000.0) * 0.3

    order = credit.get("order")
    if isinstance(order, int):
        if order <= 2:
            score += 35.0
        elif order <= 5:
            score += 24.0
        elif order <= 10:
            score += 12.0
        if adult_only:
            if order == 0:
                score += 35.0
            elif order == 1:
                score += 20.0
            score += max(0, 18 - (order * 2.5))

    if credit.get("is_lead"):
        score += 18.0

    if bool(credit.get("character")) and credit.get("order") == 0:
        score += 17.0

    if _department_matches_credit(credit, department):
        score += 22.0

    if credit.get("poster_path"):
        score += 4.0

    if _is_self_or_guest_credit(credit):
        score -= 45.0

    if person_name:
        p_name = person_name.lower().strip()
        first_name = p_name.split()[0] if p_name else ""
        title_lower = (credit.get("title") or credit.get("name") or "").lower()
        if p_name in title_lower:
            score += 25.0
        elif first_name and len(first_name) > 2 and f"being {first_name}" in title_lower:
            score += 25.0
        elif first_name and len(first_name) > 2 and first_name in title_lower:
            score += 15.0

    return score

def select_known_for(credits: List[dict], department: Optional[str], limit: int = 8, adult_only: bool = False, person_name: Optional[str] = None) -> List[dict]:
    if not credits:
        return []

    normalized_department = str(department or "").strip().lower()

    ranked = sorted(
        credits,
        key=lambda credit: (known_for_score(credit, department, adult_only=adult_only, person_name=person_name), credit.get("year") or 0),
        reverse=True,
    )

    selected: List[dict] = []
    selected_ids = set()
    self_like_count = 0

    def add_from_pool(pool: List[dict], max_self_like: Optional[int] = None):
        nonlocal self_like_count
        for credit in pool:
            if len(selected) >= limit:
                break
            credit_key = (int(credit.get("id") or 0), str(credit.get("media_type") or credit.get("type") or ""))
            if credit_key in selected_ids:
                continue

            is_self_like = _is_self_or_guest_credit(credit)
            if max_self_like is not None and is_self_like and self_like_count >= max_self_like:
                continue

            selected.append(credit)
            selected_ids.add(credit_key)
            if is_self_like:
                self_like_count += 1

    primary_pool = [
        credit for credit in ranked
        if _department_matches_credit(credit, department)
        and not _is_self_or_guest_credit(credit)
        and not (normalized_department == "acting" and _is_voice_credit(credit))
    ]
    secondary_pool = [
        credit for credit in ranked
        if _department_matches_credit(credit, department)
    ]
    tertiary_pool = [
        credit for credit in ranked
        if not _is_self_or_guest_credit(credit)
    ]

    add_from_pool(primary_pool, max_self_like=0)
    add_from_pool(secondary_pool, max_self_like=1)
    add_from_pool(tertiary_pool, max_self_like=1)
    add_from_pool(ranked, max_self_like=1)

    return selected[:limit]

def resolve_person_known_for_backdrop(
    db: Session,
    tmdb_client: Any,
    credits: List[dict],
    preferred_languages: List[str],
    department: Optional[str] = None,
    adult_only: bool = False,
    respect_credit_order: bool = False,
) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Resolves the best backdrop image for a person based on their credits."""
    candidates: List[tuple[int, str, int, str]] = []
    seen_media = set()
    max_scan = 5 if adult_only else 3

    ranked_credits = list(credits or []) if respect_credit_order else sorted(
        credits or [],
        key=lambda credit: (
            known_for_score(credit, department, adult_only=adult_only),
            int(str((credit.get("release_date") if credit.get("media_type") == "movie" else credit.get("first_air_date")) or "0")[:4] or 0),
        ),
        reverse=True,
    )

    for credit in ranked_credits:
        media_type = credit.get("media_type")
        credit_id = credit.get("tmdb_id") or credit.get("id")
        if media_type not in {"movie", "tv"} or not credit_id:
            continue
        try:
            parsed_credit_id = int(credit_id)
        except (TypeError, ValueError):
            continue

        media_key = (media_type, parsed_credit_id)
        if media_key in seen_media:
            continue
        seen_media.add(media_key)
        if len(seen_media) > max_scan:
            break

        # Fetch details through TMDBClient (automatically goes through APICache)
        raw_data = None
        try:
            raw_data = tmdb_client.get_details(
                parsed_credit_id,
                "movie" if media_type == "movie" else "tv",
                language=preferred_languages[0]
            )
        except Exception:
            pass

        backdrop_path = image_processing_service.pick_backdrop_path(raw_data, preferred_language=preferred_languages[0]) if raw_data else None
        if backdrop_path:
            candidates.append((
                image_processing_service.backdrop_resolution_from_raw(raw_data, backdrop_path),
                backdrop_path,
                parsed_credit_id,
                media_type
            ))
            continue

        fallback_backdrop = credit.get("backdrop_path")
        if fallback_backdrop:
            candidates.append((0, fallback_backdrop, parsed_credit_id, media_type))

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[0]
    return best[1], best[2], best[3]


def merge_images(existing: Optional[list[str]], new_images: list[str]) -> list[str]:
    if not existing:
        existing = []
    seen = set()
    res_list = []

    def normalize_key(img: str) -> str:
        if img.startswith(("http://", "https://")):
            return img.split("?")[0].lower()
        return img.split("/")[-1].split("?")[0].lower()

    for img in existing:
        if not img:
            continue
        norm = normalize_key(img)
        if norm not in seen:
            seen.add(norm)
            res_list.append(img)
    for img in new_images:
        if not img:
            continue
        norm = normalize_key(img)
        if norm not in seen:
            seen.add(norm)
            res_list.append(img)
    return res_list

