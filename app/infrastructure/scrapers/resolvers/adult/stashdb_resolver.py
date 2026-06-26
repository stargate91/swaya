import logging
from typing import Optional, Dict, List, Any, Tuple
from app.shared_kernel.enums import Provider, ItemStatus
from app.domains.library.models import MediaItem

logger = logging.getLogger(__name__)

HASH_QUERY = """
query FindSceneByHash($hash: String!) {
  queryScenes(input: { fingerprints: { value: [$hash], modifier: EQUALS }, page: 1, per_page: 1 }) {
    scenes {
      id
      title
      details
      duration
      date
      tags { name }
      studio { id name images { url } }
      performers {
        performer {
          id name gender scene_count birth_date images { url } ethnicity hair_color eye_color height
          measurements { band_size cup_size waist hip }
        }
      }
      images { url }
    }
  }
}
"""

SEARCH_QUERY = """
query SearchScenes($q: String!) {
  searchScene(term: $q) {
    id
    title
    details
    date
    duration
    tags { name }
    studio { id name images { url } }
    performers {
      performer {
        id name gender scene_count birth_date images { url } ethnicity hair_color eye_color height
        measurements { band_size cup_size waist hip }
      }
    }
    images { url }
  }
}
"""

class StashDbResolver:
    """
    Submodule to resolve matches from StashDB API.
    """
    def __init__(self, scraper):
        self.scraper = scraper
        self.provider = Provider.STASHDB

    def is_configured(self) -> bool:
        return bool(self.scraper.get_setting('stashdb_api_key'))

    def resolve_by_hash(
        self,
        item: MediaItem,
        hash_type: str,
        hash_value: str,
        validate_fn
    ) -> Tuple[Optional[dict], Optional[ItemStatus]]:
        if not hash_value:
            return None, None

        cache_key = f'{self.provider.value}/hash/v4/{hash_type}/{hash_value}'
        cached = self.scraper.cache.get(self.provider, cache_key)
        if cached is not None:
            if cached and cached.get("scene"):
                scene_data = cached["scene"]
                status = validate_fn(item, scene_data, ItemStatus(cached["status"]))
                return scene_data, status
            return None, None

        try:
            res = self.scraper.execute_query(HASH_QUERY, {'hash': hash_value})
            scenes = res.get('queryScenes', {}).get('scenes') if res else []
            candidate = scenes[0] if scenes else None
            if candidate:
                if hash_type == 'oshash':
                    status = ItemStatus.MATCHED
                else:  # phash
                    if item.duration and candidate.get("duration"):
                        diff = abs(float(item.duration) - float(candidate["duration"]))
                        if diff <= 15:
                            status = ItemStatus.MATCHED
                        elif diff <= 300:
                            status = ItemStatus.UNCERTAIN
                        else:
                            status = None
                    else:
                        status = ItemStatus.MATCHED
                
                if status:
                    status = validate_fn(item, candidate, status)
                
                if status:
                    self.scraper.cache.set(self.provider, cache_key, {"scene": candidate, "status": status.value})
                    return candidate, status
                else:
                    self.scraper.cache.set(self.provider, cache_key, {})
            else:
                self.scraper.cache.set(self.provider, cache_key, {})
        except Exception as exc:
            logger.error('%s %s hash query failed: %s', self.provider.value, hash_type.upper(), exc)

        return None, None

    def search_by_text(self, search_title: str) -> List[dict]:
        cache_key_search = f'{self.provider.value}/scenes/search/v4/{search_title.strip().lower()}'
        cached_search = self.scraper.cache.get(self.provider, cache_key_search)
        if cached_search is not None:
            return cached_search

        try:
            res = self.scraper.execute_query(SEARCH_QUERY, {'q': search_title})
            scenes = res.get('searchScene', []) if res else []
            self.scraper.cache.set(self.provider, cache_key_search, scenes or [])
            return scenes or []
        except Exception as exc:
            logger.error('Text query failed for provider %s: %s', self.provider.value, exc)
            return []
