import logging
from typing import Optional, Dict, List, Any, Tuple
from app.shared_kernel.enums import Provider, ItemStatus
from app.domains.library.models import MediaItem
from app.shared_kernel.constants import PORNDB_API_BASE, SCRAPER_REQUEST_TIMEOUT
from app.infrastructure.scrapers.resolvers.adult.stashdb_resolver import SEARCH_QUERY

logger = logging.getLogger(__name__)

class PornDbResolver:
    """
    Submodule to resolve matches from PornDB API.
    """
    def __init__(self, scraper):
        self.scraper = scraper
        self.provider = Provider.PORNDB

    def is_configured(self) -> bool:
        return bool(
            self.scraper.get_setting('porndb_api_key') or
            self.scraper.get_setting('porndb_api_token')
        )

    def resolve_by_hash(
        self,
        item: MediaItem,
        hash_type: str,
        hash_value: str,
        validate_fn
    ) -> Tuple[Optional[dict], Optional[ItemStatus]]:
        if not hash_value or hash_type != 'oshash':
            return None, None

        api_token = self.scraper.get_setting('porndb_api_key') or self.scraper.get_setting('porndb_api_token')
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        cache_key = f'porndb/scenes/hash/v4/{hash_type.lower()}/{hash_value}'
        cached = self.scraper.cache.get(self.provider, cache_key)
        if cached is not None:
            if cached and cached.get("scene"):
                scene_data = cached["scene"]
                status = validate_fn(item, scene_data, ItemStatus(cached["status"]))
                return scene_data, status
            return None, None

        url = f'{PORNDB_API_BASE}/scenes/hash/{hash_value}?type={hash_type.upper()}'
        try:
            resp = self.scraper.session.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
            if resp.status_code == 200:
                res_json = resp.json()
                candidate = (res_json or {}).get('data')
                if candidate:
                    status = validate_fn(item, candidate, ItemStatus.MATCHED)
                    self.scraper.cache.set(self.provider, cache_key, {"scene": candidate, "status": status.value})
                    return candidate, status
                else:
                    self.scraper.cache.set(self.provider, cache_key, {})
            else:
                self.scraper.cache.set(self.provider, cache_key, {})
        except Exception as exc:
            logger.error('PornDB %s query failed for scenes: %s', hash_type.upper(), exc)

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
