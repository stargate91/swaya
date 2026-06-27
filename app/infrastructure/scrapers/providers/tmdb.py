import logging
import time
import random
from typing import Optional, List, Dict, Any

from app.shared_kernel.enums import Provider, MediaType
from app.shared_kernel.language import LanguageService
from app.infrastructure.scrapers.support.base import BaseScraper
from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer

from app.shared_kernel.constants import TMDB_API_BASE, DEFAULT_FALLBACK_LANGUAGE, TMDB_MOVIE_APPEND_PARTS, TMDB_TV_APPEND_PARTS, SCRAPER_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class TMDBScraper(BaseScraper):
    """TMDB-specific metadata retriever and parser utilizing ScraperNormalizer."""

    def __init__(self, settings_port, cache_service=None):
        super().__init__(settings_port, cache_service, Provider.TMDB)

    def _call_api(self, endpoint: str, params: Dict[str, Any], max_retries: int = 3, force_refresh: bool = False) -> Dict[str, Any]:
        """Central API caller with caching and rate limit (429) handling."""
        api_key = self.get_setting("tmdb_api_key")
        if not api_key:
            logger.warning("TMDB API key not configured.")
            return {}

        p = params.copy()
        if 'api_key' not in p:
            p['api_key'] = api_key

        # Generate unique cache key (exclude API key for security)
        cache_params = p.copy()
        cache_params.pop('api_key', None)
        sorted_params = sorted(cache_params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        cache_key = f"tmdb{endpoint}?{param_str}"

        # Check Cache
        cached_data = self.cache.get(Provider.TMDB, cache_key, force_refresh=force_refresh)
        if cached_data:
            if cached_data.get("cached_error"):
                return {}
            return cached_data

        url = f"{TMDB_API_BASE}{endpoint}"
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=p, timeout=SCRAPER_REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    self.cache.set(Provider.TMDB, cache_key, data, status_code=200, external_id=str(data.get("id")))
                    return data
                elif resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 1))
                    logger.warning(f"TMDB Rate Limit (429). Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                else:
                    self.cache.set(Provider.TMDB, cache_key, {}, status_code=resp.status_code)
                    return {}
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"TMDB API Error ({endpoint}): {e}")
                    raise e
                time.sleep(2 ** attempt + random.uniform(0, 0.5))
        
        return {}

    def search(self, query: str, item_type: str = "movie", year: Optional[int] = None, language: Optional[str] = None, include_adult: bool = False, page: int = 1) -> List[Dict[str, Any]]:
        """Search TMDB (Movie or TV Show)."""
        if not query:
            return []

        resolved_lang = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        endpoint = "/search/movie" if item_type == "movie" else "/search/tv"
        params = {
            "query": query,
            "include_adult": "true" if include_adult else "false",
            "page": max(1, int(page or 1)),
            "language": resolved_lang
        }
        if year:
            key = "primary_release_year" if item_type == "movie" else "first_air_date_year"
            params[key] = year

        data = self._call_api(endpoint, params)
        return data.get("results", [])

    def search_person(self, query: str, language: str = "en-US", include_adult: bool = False, page: int = 1) -> List[Dict[str, Any]]:
        """Search for people (actors/directors) on TMDB."""
        if not query:
            return []

        endpoint = "/search/person"
        params = {
            "query": query,
            "language": language,
            "include_adult": "true" if include_adult else "false",
            "page": max(1, int(page or 1)),
        }
        data = self._call_api(endpoint, params)
        return data.get("results", [])

    def find_by_imdb(self, imdb_id: str, language: str = "en-US") -> Optional[Dict[str, Any]]:
        """Find a movie or TV show by its IMDb ID."""
        if not imdb_id:
            return None

        params = {
            "external_source": "imdb_id",
            "language": language
        }
        data = self._call_api(f"/find/{imdb_id}", params)
        
        movies = data.get("movie_results", [])
        tv = data.get("tv_results", [])
        
        if movies: return {**movies[0], "item_type": "movie"}
        if tv: return {**tv[0], "item_type": "tv"}
        return None

    def get_details(
        self,
        tmdb_id: int,
        item_type: str,
        language: Optional[str] = None,
        include_images: bool = True,
        append_parts: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Retrieve detailed information about a movie or TV show."""
        endpoint = f"/movie/{tmdb_id}" if item_type == "movie" else f"/tv/{tmdb_id}"
        resolved_lang = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        
        if append_parts is None:
            if item_type == "movie":
                append_parts = list(TMDB_MOVIE_APPEND_PARTS)
            else:
                append_parts = list(TMDB_TV_APPEND_PARTS)
            if include_images:
                append_parts.append("images")

        append = ",".join(append_parts)
        normalized_lang = resolved_lang.split("-", 1)[0].strip() or DEFAULT_FALLBACK_LANGUAGE
        include_image_language = ",".join(dict.fromkeys([normalized_lang, DEFAULT_FALLBACK_LANGUAGE, "null"]))
        include_video_language = ",".join(dict.fromkeys([normalized_lang, DEFAULT_FALLBACK_LANGUAGE, "null"]))

        params = {
            "language": resolved_lang,
            "append_to_response": append,
            "include_video_language": include_video_language,
        }
        if include_images:
            params["include_image_language"] = include_image_language

        try:
            return self._call_api(endpoint, params, force_refresh=force_refresh)
        except Exception as e:
            # Fallback 1: Try without credits/translations
            try:
                reduced_parts = [p for p in append_parts if p not in ("credits", "aggregate_credits", "translations")]
                params["append_to_response"] = ",".join(reduced_parts)
                return self._call_api(endpoint, params, force_refresh=force_refresh)
            except Exception:
                # Fallback 2: Try with no appends at all
                try:
                    params.pop("append_to_response", None)
                    return self._call_api(endpoint, params, force_refresh=force_refresh)
                except Exception:
                    pass
            raise e

    def get_episode_details(self, tv_id: int, season_number: int, episode_number: int, language: str = "en-US", force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve details for a specific episode."""
        endpoint = f"/tv/{tv_id}/season/{season_number}/episode/{episode_number}"
        params = {
            "language": language,
            "append_to_response": "credits,external_ids,images,translations,videos"
        }
        return self._call_api(endpoint, params, force_refresh=force_refresh)

    def get_season_details(self, tv_id: int, season_number: int, language: str = "en-US", force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve details for a specific season."""
        endpoint = f"/tv/{tv_id}/season/{season_number}"
        normalized_lang = str(language or DEFAULT_FALLBACK_LANGUAGE).split("-", 1)[0].strip() or DEFAULT_FALLBACK_LANGUAGE
        include_image_language = ",".join(dict.fromkeys([normalized_lang, DEFAULT_FALLBACK_LANGUAGE, "null"]))
        params = {
            "language": language,
            "append_to_response": "external_ids,videos,images",
            "include_image_language": include_image_language,
        }
        return self._call_api(endpoint, params, force_refresh=force_refresh)

    def get_person_images(self, person_id: int, force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve all available profile pictures for a person."""
        endpoint = f"/person/{person_id}/images"
        return self._call_api(endpoint, {}, force_refresh=force_refresh)

    def get_person_details(self, person_id: int, language: str = "en-US", force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve detailed information about a person."""
        endpoint = f"/person/{person_id}"
        params = {
            "language": language,
            "append_to_response": "images,translations,external_ids,combined_credits"
        }
        try:
            return self._call_api(endpoint, params, force_refresh=force_refresh)
        except Exception as e:
            # Fallback 1: Try without combined_credits
            try:
                params["append_to_response"] = "images,translations,external_ids"
                return self._call_api(endpoint, params, force_refresh=force_refresh)
            except Exception:
                # Fallback 2: Try with no appends at all
                try:
                    params.pop("append_to_response", None)
                    return self._call_api(endpoint, params, force_refresh=force_refresh)
                except Exception:
                    pass
            
            # If all original language attempts failed, try English fallback
            normalized_lang = str(language or DEFAULT_FALLBACK_LANGUAGE).split("-", 1)[0].strip() or DEFAULT_FALLBACK_LANGUAGE
            if normalized_lang != DEFAULT_FALLBACK_LANGUAGE:
                params["language"] = f"{DEFAULT_FALLBACK_LANGUAGE}-US"
                params["append_to_response"] = "images,translations,external_ids,combined_credits"
                try:
                    return self._call_api(endpoint, params, force_refresh=force_refresh)
                except Exception:
                    try:
                        params["append_to_response"] = "images,translations,external_ids"
                        return self._call_api(endpoint, params, force_refresh=force_refresh)
                    except Exception:
                        try:
                            params.pop("append_to_response", None)
                            return self._call_api(endpoint, params, force_refresh=force_refresh)
                        except Exception:
                            pass
            raise e

    def fetch_movie(self, movie_id: str, language: Optional[str] = None, force_refresh: bool = False) -> Optional[dict]:
        """Fetches movie details from TMDB with caching and localization."""
        data = self.get_details(int(movie_id), "movie", language=language, force_refresh=force_refresh)
        return data if data else None

    def fetch_tv(self, tv_id: str, language: Optional[str] = None, force_refresh: bool = False) -> Optional[dict]:
        """Fetches TV show details from TMDB with caching and localization."""
        data = self.get_details(int(tv_id), "tv", language=language, force_refresh=force_refresh)
        return data if data else None

    def get_trending(self, media_type: str, time_window: str = "day", language: Optional[str] = None) -> Dict[str, Any]:
        """Fetch trending items from TMDB."""
        resolved_lang = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        endpoint = f"/trending/{media_type}/{time_window}"
        return self._call_api(endpoint, {"language": resolved_lang})

    def discover(self, media_type: str, language: Optional[str] = None, sort_by: str = "popularity.desc", include_adult: bool = False, with_companies: Optional[str] = None, page: Optional[int] = None) -> Dict[str, Any]:
        """Discover media items from TMDB."""
        resolved_lang = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        endpoint = f"/discover/{media_type}"
        params = {"language": resolved_lang, "sort_by": sort_by, "include_adult": str(include_adult).lower()}
        if with_companies:
            params["with_companies"] = with_companies
        if page is not None:
            params["page"] = str(page)
        return self._call_api(endpoint, params)

    def get_collection_details(self, collection_id: int, language: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Retrieve details for a specific movie collection/saga."""
        resolved_lang = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        endpoint = f"/collection/{collection_id}"
        params = {
            "language": resolved_lang,
            "append_to_response": "images",
        }
        if resolved_lang:
            lang_short = resolved_lang.split("-")[0]
            params["include_image_language"] = f"{lang_short},en,null"
        return self._call_api(endpoint, params, force_refresh=force_refresh)


