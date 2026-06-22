import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

def normalize_tag_names(raw_tags: Any) -> List[str]:
    names: Dict[str, str] = {}
    for entry in raw_tags or []:
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            nested = entry.get("tag")
            name = entry.get("name") or (nested.get("name") if isinstance(nested, dict) else None)
        else:
            name = None

        normalized = str(name or "").strip()
        if normalized:
            names.setdefault(normalized.casefold(), normalized)
    return list(names.values())


def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse date strings from APIs into datetime objects."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            continue
    return None

class ScraperNormalizer:
    """
    Central normalization class that processes raw JSON responses from various APIs
    and standardizes them into clean dictionaries matching our internal DB schemas.
    """

    @staticmethod
    def normalize_tmdb_movie(raw: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Normalizes raw TMDB movie payload."""
        # Main match fields
        match_data = {
            "imdb_id": raw.get("imdb_id"),
            "original_title": raw.get("original_title"),
            "release_date": safe_parse_date(raw.get("release_date")),
            "runtime": raw.get("runtime"),
            "popularity": raw.get("popularity"),
            "rating_tmdb": raw.get("vote_average"),
            "vote_count_tmdb": raw.get("vote_count"),
            "budget": raw.get("budget"),
            "revenue": raw.get("revenue"),
            "release_status": raw.get("status"),
            "is_adult": raw.get("adult", False),
            "backdrop_path": raw.get("backdrop_path"),
            "raw_metadata": raw,
            "fetched_locales": [language]
        }

        # Localization fields
        localization = {
            "title": raw.get("title") or raw.get("original_title") or "Unknown",
            "tagline": raw.get("tagline"),
            "overview": raw.get("overview"),
            "poster_path": raw.get("poster_path"),
            "genres": [g["name"] for g in raw.get("genres") or []]
        }

        # Studios list
        studios = []
        for comp in raw.get("production_companies") or []:
            if comp.get("name"):
                studios.append({
                    "name": comp["name"],
                    "logo_path": comp.get("logo_path"),
                    "parent": None
                })

        # Collection details
        collection = None
        belongs_to_collection = raw.get("belongs_to_collection")
        if belongs_to_collection:
            collection = {
                "external_id": str(belongs_to_collection["id"]),
                "name": belongs_to_collection.get("name"),
                "backdrop_path": belongs_to_collection.get("backdrop_path")
            }

        # Performers / Cast
        performers = []
        credits = raw.get("credits") or {}
        for cast_member in credits.get("cast") or []:
            performers.append({
                "name": cast_member.get("name"),
                "profile_path": cast_member.get("profile_path"),
                "gender": cast_member.get("gender"),
                "is_adult": False,
                "tmdb_id": str(cast_member["id"]),
                "character": cast_member.get("character"),
                "performer_details": None
            })

        return {
            "match": match_data,
            "localization": localization,
            "studios": studios,
            "collection": collection,
            "performers": performers
        }

    @staticmethod
    def normalize_porndb_movie(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a PornDB Movies API SceneResource as an adult movie."""
        movie = dict(raw or {})

        def image_variant(value: Any) -> Optional[str]:
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                return (
                    value.get("full")
                    or value.get("large")
                    or value.get("medium")
                    or value.get("small")
                )
            return None

        poster = (
            movie.get("poster_image")
            or movie.get("poster")
            or movie.get("image")
            or image_variant(movie.get("posters"))
        )
        backdrop = image_variant(movie.get("background"))

        site = movie.get("site") or {}
        if site.get("name") and not movie.get("studio"):
            movie["studio"] = {
                "name": site["name"],
                "logo": (
                    site.get("logo")
                    or site.get("image")
                    or image_variant(site.get("images"))
                ),
                "parent": site.get("parent"),
            }

        movie["background"] = backdrop
        movie["posters"] = {"large": poster} if poster else {}
        norm = ScraperNormalizer.normalize_adult_scene("porndb", {"data": movie})
        norm["match"]["backdrop_path"] = backdrop

        duration = movie.get("duration")
        try:
            norm["match"]["runtime"] = max(1, round(float(duration) / 60)) if duration else None
        except (TypeError, ValueError):
            norm["match"]["runtime"] = None

        links = movie.get("links") or {}
        imdb_value = next(
            (
                value
                for key, value in links.items()
                if str(key).casefold() in ("imdb", "imdb.com") and value
            ),
            None,
        )
        imdb_match = re.search(r"tt\d{7,10}", str(imdb_value or ""))
        norm["match"]["imdb_id"] = imdb_match.group(0) if imdb_match else None
        norm["match"]["raw_metadata"] = raw
        norm["localization"]["poster_path"] = poster
        return norm
    @staticmethod
    def normalize_adult_scene(provider: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes raw adult scene payloads from StashDB, PornDB, or FansDB.
        Standardizes schemas (REST vs GraphQL) to a single internal format.
        """
        title = "Unknown Scene"
        overview = None
        release_date = None
        rating_val = None
        backdrop_url = None
        poster_url = None
        studio_data = None
        performers_raw = []
        tags_raw = []
        def image_variant(value: Any) -> Optional[str]:
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                return next((v for v in (value.get("full"), value.get("large"), value.get("medium"), value.get("small")) if v), None)
            return None

        def first_image_url(images: Any) -> Optional[str]:
            if isinstance(images, list) and images:
                first = images[0]
                if isinstance(first, dict):
                    return first.get("url") or image_variant(first)
                if isinstance(first, str):
                    return first
            return None
        # 1. Extract based on Stash-compatible GraphQL schema (StashDB & FansDB/PornDB GraphQL)
        if "findScene" in raw or "id" in raw:
            scene = raw.get("findScene") or raw
            title = scene.get("title") or "Unknown Scene"
            overview = scene.get("details") or scene.get("description")
            release_date = safe_parse_date(scene.get("date"))
            
            rating_val = scene.get("rating_porndb") if provider == "porndb" else None
            
            # Images
            images = scene.get("images") or []
            poster_url_temp = (
                image_variant(scene.get("posters"))
                or scene.get("poster_image")
                or scene.get("poster")
                or scene.get("image")
                or first_image_url(images)
            )
            backdrop_url = (
                image_variant(scene.get("background"))
                or image_variant(scene.get("background_back"))
                or scene.get("back_image")
                or scene.get("image")
                or first_image_url(images)
                or poster_url_temp
            )
            poster_url = backdrop_url
            
            studio_data = scene.get("studio") or scene.get("site")
            performers_raw = [
                p.get("performer") or p
                for p in (scene.get("performers") or [])
                if isinstance(p, dict) and (p.get("performer") or p.get("name"))
            ]
            tags_raw = scene.get("tags") or []

        # 2. Extract based on standard REST schemas (PornDB/FansDB REST if returned in 'data')
        elif "data" in raw:
            scene = raw["data"]
            title = scene.get("title") or "Unknown Scene"
            overview = scene.get("description") or scene.get("details")
            release_date = safe_parse_date(scene.get("date"))
            rating_val = scene.get("rating_porndb") if provider == "porndb" else None
            poster_url_temp = image_variant(scene.get("posters")) or scene.get("poster_image") or scene.get("poster") or scene.get("image")
            backdrop_url = image_variant(scene.get("background")) or image_variant(scene.get("background_back")) or scene.get("back_image") or scene.get("image") or poster_url_temp
            poster_url = backdrop_url
            studio_data = scene.get("studio") or scene.get("site")
            performers_raw = scene.get("performers") or []
            tags_raw = scene.get("tags") or []

        # Normalize Studio details
        studios = []
        if studio_data and studio_data.get("name"):
            s_logo = studio_data.get("image_path") or studio_data.get("logo")
            # If images is list (Stash GraphQL)
            if not s_logo and studio_data.get("images"):
                s_logo = studio_data["images"][0].get("url")

            parent = None
            parent_data = studio_data.get("parent")
            if parent_data and parent_data.get("name"):
                p_logo = parent_data.get("image_path") or parent_data.get("logo")
                if not p_logo and parent_data.get("images"):
                    p_logo = parent_data["images"][0].get("url")
                parent = {
                    "name": parent_data["name"],
                    "logo_path": p_logo
                }

            studios.append({
                "name": studio_data["name"],
                "logo_path": s_logo,
                "parent": parent
            })

        # Normalize Performers
        performers = []
        for cast_member in performers_raw:
            p_name = cast_member.get("name")
            if not p_name:
                continue
            
            p_gender = cast_member.get("gender")
            gender_int = 1 if p_gender == "FEMALE" else (2 if p_gender == "MALE" else None)
            
            p_image = cast_member.get("image_path") or cast_member.get("image") or cast_member.get("photo")
            # If images is list
            if not p_image and cast_member.get("images"):
                p_image = cast_member["images"][0].get("url")

            # Extract measurements
            measurements = cast_member.get("measurements")
            # StashDB GraphQL returns measurements as a dict
            if isinstance(measurements, dict):
                parts = []
                band = measurements.get("band_size")
                cup = measurements.get("cup_size")
                bust = f"{band}{cup}" if band or cup else ""
                if bust:
                    parts.append(bust)
                waist = measurements.get("waist")
                if waist:
                    parts.append(str(waist))
                hip = measurements.get("hip")
                if hip:
                    parts.append(str(hip))
                measurements = "-".join(parts) if parts else None

            performer_details = {
                "hair_color": cast_member.get("hair_color") or cast_member.get("hair"),
                "eye_color": cast_member.get("eye_color") or cast_member.get("eye"),
                "ethnicity": cast_member.get("ethnicity"),
                "height": cast_member.get("height"),
                "scene_count": cast_member.get("scene_count"),
                "rating_porndb": cast_member.get("rating_porndb"),
                "weight": cast_member.get("weight"),
                "measurements": measurements
            }

            performers.append({
                "name": p_name,
                "profile_path": p_image,
                "gender": gender_int,
                "is_adult": True,
                "tmdb_id": None,
                "character": None,
                "performer_details": performer_details,
                "provider": provider,
                "external_id": str(cast_member.get("id")) if cast_member.get("id") else None
            })

        # Main match fields
        match_data = {
            "imdb_id": None,
            "original_title": title,
            "release_date": release_date,
            "runtime": None,
            "popularity": None,
            "rating_porndb": float(rating_val) if provider == "porndb" and rating_val is not None else None,
            "is_adult": True,
            "backdrop_path": backdrop_url,
            "suggested_tags": normalize_tag_names(tags_raw),
            "raw_metadata": raw,
            "fetched_locales": ["en"]
        }

        # Localization fields
        localization = {
            "title": title,
            "tagline": None,
            "overview": overview,
            "poster_path": poster_url or backdrop_url,
            "genres": []
        }

        return {
            "match": match_data,
            "localization": localization,
            "studios": studios,
            "collection": None,
            "performers": performers
        }
