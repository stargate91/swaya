import logging
from typing import Optional

from app.shared_kernel.enums import Provider, MediaType
from app.infrastructure.scrapers.support.base import BaseScraper
from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer

from app.shared_kernel.constants import FANSDB_DEFAULT_ENDPOINT, SCRAPER_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class FansDBScraper(BaseScraper):
    """FansDB-specific metadata retriever and parser utilizing GraphQL and ScraperNormalizer."""

    def __init__(self, db_session, cache_service=None):
        super().__init__(db_session, cache_service, Provider.FANSDB)

    def fetch_scene(self, scene_id: str, force_refresh: bool = False) -> Optional[dict]:
        """Queries FansDB GraphQL endpoint for scene info. Always mapped to English locale."""
        endpoint = self.get_setting("fansdb_endpoint", FANSDB_DEFAULT_ENDPOINT)
        api_token = self.get_setting("fansdb_api_key")
        if not api_token:
            logger.warning("FansDB API key/token not configured.")
            return None

        cache_key = f"fansdb/scene/v4/{scene_id}"
        cached_data = self.cache.get(Provider.FANSDB, cache_key, force_refresh=force_refresh)
        if cached_data:
            if cached_data.get("cached_error"):
                return None
            return cached_data

        # Using Stash-compatible GraphQL schema supported by FansDB's GraphQL endpoint
        query = """
        query FindScene($id: ID!) {
          findScene(id: $id) {
            id
            title
            details
            date
            tags {
              name
            }
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
                measurements {
                  band_size
                  cup_size
                  waist
                  hip
                }
              }
            }
            images {
              url
            }
          }
        }
        """
        headers = {"ApiKey": api_token, "Content-Type": "application/json"}
        payload = {"query": query, "variables": {"id": scene_id}}

        try:
            resp = self.session.post(endpoint, json=payload, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if "errors" in result:
                    logger.error(f"GraphQL errors from FansDB: {result['errors']}")
                    return None
                data = result.get("data", {}).get("findScene")
                if data:
                    self.cache.set(Provider.FANSDB, cache_key, data, status_code=200, media_type=MediaType.SCENE, external_id=scene_id)
                    return data
                else:
                    self.cache.set(Provider.FANSDB, cache_key, {}, status_code=404, media_type=MediaType.SCENE, external_id=scene_id)
                    return None
            else:
                self.cache.set(Provider.FANSDB, cache_key, {}, status_code=resp.status_code, media_type=MediaType.SCENE, external_id=scene_id)
                return None
        except Exception as e:
            logger.error(f"Error querying FansDB GraphQL for scene {scene_id}: {e}")
            return None


