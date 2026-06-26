import logging
from typing import Optional

from app.shared_kernel.enums import Provider, MediaType
from app.infrastructure.scrapers.support.base import BaseScraper
from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer

from app.shared_kernel.constants import STASHDB_DEFAULT_ENDPOINT, SCRAPER_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class StashDBScraper(BaseScraper):
    """StashDB-specific metadata retriever and parser utilizing GraphQL and ScraperNormalizer."""

    def __init__(self, settings_port, cache_service=None):
        super().__init__(settings_port, cache_service, Provider.STASHDB)

    def fetch_scene(self, scene_id: str, force_refresh: bool = False) -> Optional[dict]:
        """Queries StashDB GraphQL endpoint for scene info. Always mapped to English locale."""
        import re
        if not re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", str(scene_id)):
            logger.debug(f"Invalid UUID for StashDB fetch_scene: {scene_id}")
            return None

        endpoint = self.get_setting("stashdb_endpoint", STASHDB_DEFAULT_ENDPOINT)
        api_key = self.get_setting("stashdb_api_key")
        if not api_key:
            logger.warning("StashDB API key not configured.")
            return None

        cache_key = f"stashdb/scene/v4/{scene_id}"
        cached_data = self.cache.get(Provider.STASHDB, cache_key, force_refresh=force_refresh)
        if cached_data:
            if cached_data.get("cached_error"):
                return None
            return cached_data

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
        headers = {"ApiKey": api_key, "Content-Type": "application/json"}
        payload = {"query": query, "variables": {"id": scene_id}}

        try:
            resp = self.session.post(endpoint, json=payload, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
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
                    self.cache.set(Provider.STASHDB, cache_key, data, status_code=200, media_type=MediaType.SCENE, external_id=scene_id)
                    return data
                else:
                    self.cache.set(Provider.STASHDB, cache_key, {}, status_code=404, media_type=MediaType.SCENE, external_id=scene_id)
                    return None
            else:
                self.cache.set(Provider.STASHDB, cache_key, {}, status_code=resp.status_code, media_type=MediaType.SCENE, external_id=scene_id)
                return None
        except Exception as e:
            logger.error(f"Error querying StashDB GraphQL for scene {scene_id}: {e}")
            return None


