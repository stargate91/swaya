import difflib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.infrastructure.scrapers.resolver import normalize_title
from app.shared_kernel.enums import ItemStatus, MediaType, Provider, ScanMode

logger = logging.getLogger(__name__)

from app.shared_kernel.constants import PORNDB_API_BASE, SCRAPER_REQUEST_TIMEOUT


class AdultResolver:
    """Handles resolving adult scene items against StashDB, PornDB, and FansDB APIs."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def resolve_primary_scene_item(self, item: MediaItem, task_id: Optional[int] = None):
        self._resolve_adult_item(item, ScanMode.SCENES, task_id)

    def resolve_scene_item(self, item: MediaItem, task_id: Optional[int] = None):
        self.resolve_primary_scene_item(item, task_id)

    def resolve_stashdb_scene_item(self, item: MediaItem, task_id: Optional[int] = None):
        self._resolve_adult_item(item, ScanMode.SCENES, task_id, preferred_provider=Provider.STASHDB)

    def resolve_fansdb_scene_item(self, item: MediaItem, task_id: Optional[int] = None):
        self._resolve_adult_item(item, ScanMode.SCENES, task_id, preferred_provider=Provider.FANSDB)

    def resolve_porndb_scene_item(self, item: MediaItem, task_id: Optional[int] = None):
        self._resolve_adult_item(item, ScanMode.SCENES, task_id, preferred_provider=Provider.PORNDB)

    def resolve_adult_item(self, item: MediaItem, mode: ScanMode = ScanMode.SCENES, task_id: Optional[int] = None):
        self.resolve_primary_scene_item(item, task_id)

    def _configured_scene_provider_order(self) -> list[Provider]:
        from app.infrastructure.scrapers.providers.stashdb import StashDBScraper

        stash_scraper = StashDBScraper(self.db)
        order_setting = stash_scraper.get_setting('scenes_scraper_order') or 'stashdb,porndb,fansdb'
        order = []
        for value in str(order_setting).split(','):
            name = value.strip().lower()
            if name == 'stashdb':
                order.append(Provider.STASHDB)
            elif name == 'fansdb':
                order.append(Provider.FANSDB)
            elif name == 'porndb':
                order.append(Provider.PORNDB)
        return order or [Provider.STASHDB, Provider.PORNDB, Provider.FANSDB]

    def _build_scrapers_to_try(self, preferred_provider: Optional[Provider] = None):
        from app.infrastructure.scrapers.providers.fansdb import FansDBScraper
        from app.infrastructure.scrapers.providers.porndb import PornDBScraper
        from app.infrastructure.scrapers.providers.stashdb import StashDBScraper

        stash_scraper = StashDBScraper(self.db)
        porndb_scraper = PornDBScraper(self.db)
        fans_scraper = FansDBScraper(self.db)
        available = {}
        if stash_scraper.get_setting('stashdb_api_key'):
            available[Provider.STASHDB] = (stash_scraper, Provider.STASHDB)
        if porndb_scraper.get_setting('porndb_api_key') or porndb_scraper.get_setting('porndb_api_token'):
            available[Provider.PORNDB] = (porndb_scraper, Provider.PORNDB)
        if fans_scraper.get_setting('fansdb_api_key'):
            available[Provider.FANSDB] = (fans_scraper, Provider.FANSDB)

        if preferred_provider:
            selected = [available[preferred_provider]] if preferred_provider in available else []
            return selected

        for provider in self._configured_scene_provider_order():
            if provider in available:
                return [available[provider]]
        return []

    def _extract_scene_search_queries(self, item: MediaItem) -> list[str]:
        parsed = item.parsed_info or {}
        fn_data = parsed.get('fn') or {}
        it_data = parsed.get('it') or {}
        fd_data = parsed.get('fd') or {}
        search_title = fn_data.get('title') or fd_data.get('title') or it_data.get('title')
        return [search_title] if search_title else []

    def _persist_scene_match(self, *, item: MediaItem, provider: Provider, scraper, scene_data: dict, confidence: float):
        self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
        self.db.query(MetadataMatch).filter(
            MetadataMatch.provider == provider,
            MetadataMatch.external_id == str(scene_data['id']),
            MetadataMatch.media_type == MediaType.SCENE,
        ).delete()

        from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer
        from app.infrastructure.scrapers.support.persistence import ScraperPersister

        if provider == Provider.PORNDB:
            scene_data = scraper.enrich_scene_ratings(scene_data)
        normalized = ScraperNormalizer.normalize_adult_scene(provider.value, scene_data)
        persister = ScraperPersister(self.db)
        match = persister.persist_normalized_scene(provider, str(scene_data['id']), normalized, media_type=MediaType.SCENE)
        match.media_item_id = item.id
        match.confidence_score = confidence
        return match

    def _resolve_adult_item(self, item: MediaItem, mode: ScanMode = ScanMode.SCENES, task_id: Optional[int] = None, preferred_provider: Optional[Provider] = None):
        scrapers_to_try = self._build_scrapers_to_try(preferred_provider)
        logger.info('[adult:%s] Resolving %s | file=%s | md5=%s | oshash=%s', mode.value, item.id, item.filename, (item.hash_md5 or '')[:12], (item.hash_oshash or '')[:12])
        logger.info('[adult:%s] Providers to try: %s', mode.value, [provider.value for _scraper, provider in scrapers_to_try])

        if not scrapers_to_try:
            logger.warning('No adult metadata provider API key configured.')
            item.status = ItemStatus.NO_MATCH
            self.db.flush()
            return

        for scraper, provider in scrapers_to_try:
            scene_data = None

            if provider in (Provider.STASHDB, Provider.FANSDB):
                hash_query = """
                query FindSceneByHash($hash: String!) {
                  queryScenes(input: { fingerprints: { value: [$hash], modifier: EQUALS }, page: 1, per_page: 1 }) {
                    scenes {
                      id
                      title
                      details
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
                for hash_type, hash_value in [('md5', item.hash_md5), ('oshash', item.hash_oshash)]:
                    if scene_data or not hash_value:
                        continue
                    logger.info('[adult:%s] Trying %s %s lookup for %s', mode.value, provider.value, hash_type.upper(), item.filename)
                    cache_key = f'{provider.value}/hash/v3/{hash_type}/{hash_value}'
                    cached = scraper.cache.get(provider, cache_key)
                    if cached is not None:
                        scene_data = cached or None
                        continue
                    try:
                        res = scraper.execute_query(hash_query, {'hash': hash_value})
                        scenes = res.get('queryScenes', {}).get('scenes') if res else []
                        scene_data = scenes[0] if scenes else None
                        scraper.cache.set(provider, cache_key, scene_data or {})
                    except Exception as exc:
                        logger.error('%s %s hash query failed: %s', provider.value, hash_type.upper(), exc)
            elif provider == Provider.PORNDB and item.hash_oshash:
                api_token = scraper.get_setting('porndb_api_key') or scraper.get_setting('porndb_api_token')
                headers = {
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
                cache_key = f'porndb/scenes/hash/oshash/{item.hash_oshash}'
                cached = scraper.cache.get(provider, cache_key)
                if cached is not None:
                    scene_data = cached or None
                else:
                    url = f'{PORNDB_API_BASE}/scenes/hash/{item.hash_oshash}?type=OSHASH'
                    try:
                        resp = scraper.session.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
                        logger.info('[adult:%s] PornDB GET %s -> status %s', mode.value, url, resp.status_code)
                        if resp.status_code == 200:
                            res_json = resp.json()
                            scene_data = (res_json or {}).get('data')
                        scraper.cache.set(provider, cache_key, scene_data or {})
                    except Exception as exc:
                        logger.error('PornDB OSHASH query failed for scenes: %s', exc)

            if scene_data:
                logger.info('[adult:%s] Hash lookup matched %s -> provider=%s external_id=%s title=%s', mode.value, item.filename, provider.value, scene_data.get('id'), scene_data.get('title'))
                self._persist_scene_match(item=item, provider=provider, scraper=scraper, scene_data=scene_data, confidence=1.0)
                item.status = ItemStatus.MATCHED
                scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=f'hash: md5={item.hash_md5}, oshash={item.hash_oshash}',
                    result_count=1,
                    details={
                        'hash_match': True,
                        'matched_scene_id': str(scene_data['id']),
                        'matched_title': scene_data.get('title'),
                        'final_status': 'matched',
                    },
                )
                self.db.flush()
                return

            search_queries = self._extract_scene_search_queries(item)
            logger.info('[adult:%s] Scene fallback queries for %s -> %s', mode.value, item.filename, search_queries)
            if not search_queries:
                continue

            best_score = 0.0
            best_scene = None
            best_query = None
            best_scenes = []

            for search_title in search_queries:
                cache_key_search = f'{provider.value}/{mode.value}/search/v3/{search_title.strip().lower()}'
                cached_search = scraper.cache.get(provider, cache_key_search)
                if cached_search is not None:
                    scenes = cached_search
                else:
                    search_query = """
                    query SearchScenes($q: String!) {
                      searchScene(term: $q) {
                        id
                        title
                        details
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
                    """
                    try:
                        res = scraper.execute_query(search_query, {'q': search_title})
                        scenes = res.get('searchScene', []) if res else []
                        scraper.cache.set(provider, cache_key_search, scenes or [])
                    except Exception as exc:
                        logger.error('Text query failed for provider %s: %s', provider.value, exc)
                        scenes = []

                if not scenes:
                    continue

                candidates = []
                for scene in scenes:
                    score = difflib.SequenceMatcher(None, normalize_title(search_title), normalize_title(scene.get('title') or '')).ratio()
                    candidates.append((score, scene))
                candidates.sort(key=lambda value: value[0], reverse=True)
                if candidates and candidates[0][0] > best_score:
                    best_score, best_scene = candidates[0]
                    best_query = search_title
                    best_scenes = scenes

            if best_scene and best_score >= 0.8:
                self._persist_scene_match(item=item, provider=provider, scraper=scraper, scene_data=best_scene, confidence=best_score)
                item.status = ItemStatus.MATCHED
                scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=best_query,
                    result_count=len(best_scenes),
                    details={
                        'hash_match': False,
                        'best_score': best_score,
                        'matched_scene_id': str(best_scene['id']),
                        'final_status': 'matched',
                    },
                )
                self.db.flush()
                return

        logger.info('[adult:%s] No match for %s after all providers', mode.value, item.filename)
        item.status = ItemStatus.NO_MATCH
        self.db.flush()
