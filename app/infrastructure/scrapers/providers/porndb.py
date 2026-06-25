import logging
import requests
from typing import Optional

from app.shared_kernel.enums import Provider, MediaType
from app.infrastructure.scrapers.support.base import BaseScraper
from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer

from app.shared_kernel.constants import PORNDB_API_BASE, PORNDB_DEFAULT_ENDPOINT, SCRAPER_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class PornDBScraper(BaseScraper):
    """ThePornDB-specific metadata retriever and parser utilizing GraphQL and ScraperNormalizer."""

    def __init__(self, db_session, cache_service=None):
        super().__init__(db_session, cache_service, Provider.PORNDB)

    def _fetch_rating(
        self,
        identifier: str,
        rating_type: str,
        force_refresh: bool = False,
    ) -> Optional[float]:
        media_type = {
            "performer": MediaType.PERSON,
            "movie": MediaType.MOVIE,
        }.get(rating_type, MediaType.SCENE)
        cache_key = f"porndb/rating/{rating_type}/v1/{identifier}"
        cached_data = self.cache.get(Provider.PORNDB, cache_key, force_refresh=force_refresh)
        if cached_data is not None:
            if cached_data.get("cached_error"):
                return None
            rating = cached_data.get("rating")
            return float(rating) if rating is not None else None

        api_token = self.get_setting("porndb_api_key") or self.get_setting("porndb_api_token")
        if not api_token:
            return None

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
        }

        try:
            url = f"{PORNDB_API_BASE}/{rating_type}s/{identifier}"
            resp = self.session.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json().get("data")
                rating = data.get("rating") if data else None
                self.cache.set(
                    Provider.PORNDB,
                    cache_key,
                    {"rating": rating},
                    status_code=200,
                    media_type=media_type,
                    external_id=str(identifier),
                )
                return float(rating) if rating is not None else None
            else:
                self.cache.set(
                    Provider.PORNDB,
                    cache_key,
                    {"cached_error": True},
                    status_code=resp.status_code,
                    media_type=media_type,
                    external_id=str(identifier),
                )
                return None
        except Exception as e:
            logger.error(f"Error fetching PornDB rating for {rating_type} {identifier}: {e}")
            return None

    def fetch_performer_rating(self, performer_id: str, force_refresh: bool = False) -> Optional[float]:
        return self._fetch_rating(performer_id, "performer", force_refresh)

    def fetch_movie_rating(self, movie_id: str, force_refresh: bool = False) -> Optional[float]:
        return self._fetch_rating(movie_id, "movie", force_refresh)

    def fetch_scene_rating(self, scene_id: str, force_refresh: bool = False) -> Optional[float]:
        return self._fetch_rating(scene_id, "scene", force_refresh)

    def enrich_movie_ratings(self, movie: dict) -> dict:
        if movie and "id" in movie:
            movie["rating_porndb"] = self.fetch_movie_rating(str(movie["id"]))
        return movie

    def enrich_scene_ratings(self, scene: dict) -> dict:
        if scene and "id" in scene:
            scene["rating_porndb"] = self.fetch_scene_rating(str(scene["id"]))
        return scene

    def get_performer_details(self, performer_id: str) -> Optional[dict]:
        details = super().get_performer_details(performer_id)
        if details:
            details["rating_porndb"] = self.fetch_performer_rating(performer_id)
        return details

    def find_movie_by_hash(self, file_hash: str, hash_type: str = "OSHASH", force_refresh: bool = False) -> Optional[dict]:
        if not file_hash:
            return None
        cache_key = f"porndb/movie/hash/v1/{hash_type.lower()}/{file_hash}"
        cached_data = self.cache.get(Provider.PORNDB, cache_key, force_refresh=force_refresh)
        if cached_data is not None:
            return None if cached_data.get("cached_error") or not cached_data else cached_data

        api_token = self.get_setting("porndb_api_key") or self.get_setting("porndb_api_token")
        if not api_token:
            return None

        try:
            response = self.session.get(
                f"{PORNDB_API_BASE}/movies/hash/{file_hash}",
                params={"type": hash_type},
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
                timeout=SCRAPER_REQUEST_TIMEOUT,
            )
            data = response.json().get("data") if response.status_code == 200 else None
            self.cache.set(
                Provider.PORNDB,
                cache_key,
                data or {},
                status_code=response.status_code,
                media_type=MediaType.MOVIE,
                external_id=str(data.get("id")) if data else None,
            )
            return self.enrich_movie_ratings(data) if data else None
        except (AttributeError, ValueError, requests.RequestException) as exc:
            logger.error(f"Error querying PornDB movie hash {file_hash}: {exc}")
    def fetch_movie(self, movie_id: str, force_refresh: bool = False) -> Optional[dict]:
        cache_key = f"porndb/movie/v1/{movie_id}"
        cached_data = self.cache.get(Provider.PORNDB, cache_key, force_refresh=force_refresh)
        if cached_data is not None:
            return None if cached_data.get("cached_error") or not cached_data else cached_data

        api_token = self.get_setting("porndb_api_key") or self.get_setting("porndb_api_token")
        if not api_token:
            return None

        try:
            url = f"{PORNDB_API_BASE}/movies/{movie_id}"
            response = self.session.get(
                url,
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
                timeout=SCRAPER_REQUEST_TIMEOUT,
            )
            data = response.json().get("data") if response.status_code == 200 else None
            self.cache.set(
                Provider.PORNDB,
                cache_key,
                data or {},
                status_code=response.status_code,
                media_type=MediaType.MOVIE,
                external_id=str(movie_id),
            )
            return self.enrich_movie_ratings(data) if data else None
        except Exception as e:
            logger.error(f"Error fetching PornDB movie {movie_id}: {e}")
            return None

    def search_movies(
        self,
        query: str,
        year: Optional[int] = None,
        per_page: int = 10,
        force_refresh: bool = False,
    ) -> list[dict]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        cache_key = f"porndb/movie/search/v1/{normalized_query.lower()}/{year or 'all'}"
        cached_data = self.cache.get(Provider.PORNDB, cache_key, force_refresh=force_refresh)
        if cached_data is not None:
            return [] if cached_data.get("cached_error") else cached_data.get("data", [])

        api_token = self.get_setting("porndb_api_key") or self.get_setting("porndb_api_token")
        if not api_token:
            return []

        params = {"q": normalized_query, "per_page": max(1, min(per_page, 25))}
        if year:
            params["year"] = year

        try:
            response = self.session.get(
                f"{PORNDB_API_BASE}/movies",
                params=params,
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
                timeout=SCRAPER_REQUEST_TIMEOUT,
            )
            movies = response.json().get("data") or [] if response.status_code == 200 else []
            self.cache.set(
                Provider.PORNDB,
                cache_key,
                {"data": movies},
                status_code=response.status_code,
                media_type=MediaType.MOVIE,
            )
            return movies
        except (AttributeError, ValueError, requests.RequestException) as exc:
            logger.error(f"Error searching PornDB movies for {normalized_query}: {exc}")
            return []

    def fetch_scene(self, scene_id: str, force_refresh: bool = False) -> Optional[dict]:
        """Queries ThePornDB GraphQL endpoint for scene info. Always mapped to English locale."""
        endpoint = self.get_setting("porndb_endpoint", PORNDB_DEFAULT_ENDPOINT)
        api_token = self.get_setting("porndb_api_key") or self.get_setting("porndb_api_token")
        if not api_token:
            logger.warning("ThePornDB API key/token not configured.")
            return None

        cache_key = f"porndb/scene/v4/{scene_id}"
        cached_data = self.cache.get(Provider.PORNDB, cache_key, force_refresh=force_refresh)
        if cached_data:
            if cached_data.get("cached_error"):
                return None
            return cached_data

        # Using Stash-compatible GraphQL schema supported by ThePornDB's GraphQL endpoint
        query = """
        query FindScene($id: ID!) {
          findScene(id: $id) {
            id
            title
            details
            date
            rating
            studio {
              id
              name
              images {
                url
              }
              parent {
                id
                name
                images {
                  url
                }
              }
            }
            performers {
              performer {
                id
                name
                gender
                scene_count
                birth_date
                images {
                  url
                }
                ethnicity
                hair_color
                eye_color
                height
                band_size
                cup_size
                waist_size
                hip_size
                urls {
                  url
                  site {
                    id
                    name
                  }
                }
                career_start_year
                career_end_year
                death_date
                country
              }
            }
            images {
              url
            }
          }
        }
        """
        headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        payload = {"query": query, "variables": {"id": scene_id}}

        try:
            resp = self.session.post(endpoint, json=payload, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if "errors" in result:
                    logger.error(f"GraphQL errors from ThePornDB: {result['errors']}")
                    return None
                data = result.get("data", {}).get("findScene")
                if data:
                    for p_entry in data.get("performers") or []:
                        perf = p_entry.get("performer")
                        if perf:
                            perf["measurements"] = {
                                "band_size": perf.get("band_size"),
                                "cup_size": perf.get("cup_size"),
                                "waist": perf.get("waist_size"),
                                "hip": perf.get("hip_size"),
                            }
                            if "urls" in perf and isinstance(perf["urls"], list):
                                perf["urls"] = [u.get("url") for u in perf["urls"] if u and u.get("url")]
                    data = self.enrich_scene_ratings(data)
                    self.cache.set(Provider.PORNDB, cache_key, data, status_code=200, media_type=MediaType.SCENE, external_id=scene_id)
                    return data
                else:
                    self.cache.set(Provider.PORNDB, cache_key, {}, status_code=404, media_type=MediaType.SCENE, external_id=scene_id)
                    return None
            else:
                self.cache.set(Provider.PORNDB, cache_key, {}, status_code=resp.status_code, media_type=MediaType.SCENE, external_id=scene_id)
                return None
        except Exception as e:
            logger.error(f"Error querying ThePornDB GraphQL for scene {scene_id}: {e}")
            return None
