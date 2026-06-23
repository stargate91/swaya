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
        queries = []
        for key in ('fn', 'fd', 'it'):
            data = parsed.get(key) or {}
            unique_title = data.get('alternative_title') or data.get('episode_title')
            if unique_title and unique_title not in queries:
                queries.append(unique_title)
        return queries

    def _persist_scene_match(
        self,
        *,
        item: MediaItem,
        provider: Provider,
        scraper,
        scene_data: dict,
        confidence: float,
        is_active: bool = True,
        clear_existing: bool = True,
        status: ItemStatus = ItemStatus.MATCHED,
        media_item_id: Optional[int] = None,
    ):
        if clear_existing:
            self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()

        from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer
        from app.infrastructure.scrapers.support.persistence import ScraperPersister

        if provider == Provider.PORNDB:
            scene_data = scraper.enrich_scene_ratings(scene_data)
        normalized = ScraperNormalizer.normalize_adult_scene(provider.value, scene_data)
        persister = ScraperPersister(self.db)
        match = persister.persist_normalized_scene(provider, str(scene_data['id']), normalized, media_type=MediaType.SCENE, media_item_id=item.id)
        match.is_active = is_active
        match.confidence_score = confidence
        item.status = status
        return match

    def _validate_hash_match(self, item: MediaItem, candidate: dict, current_status: ItemStatus) -> ItemStatus:
        if current_status != ItemStatus.MATCHED:
            return current_status

        parsed = item.parsed_info or {}
        fn_data = parsed.get("fn") or {}
        parsed_titles = [
            fn_data.get("alternative_title"),
            fn_data.get("episode_title"),
            fn_data.get("title")
        ]
        parsed_titles = [t for t in parsed_titles if t]
        if not parsed_titles:
            return current_status

        cand_title = candidate.get("title") or ""
        norm_cand = normalize_title(cand_title)
        best_ratio = 0.0
        for t in parsed_titles:
            ratio = difflib.SequenceMatcher(None, norm_cand, normalize_title(t)).ratio()
            if ratio > best_ratio:
                best_ratio = ratio

        if best_ratio < 0.5:
            logger.warning(
                'Hash match title similarity validation failed (best ratio %.2f < 0.5) for %s -> %s. Downgrading to UNCERTAIN.',
                best_ratio, item.filename, cand_title
            )
            return ItemStatus.UNCERTAIN

        return current_status

    def _resolve_adult_item(self, item: MediaItem, mode: ScanMode = ScanMode.SCENES, task_id: Optional[int] = None, preferred_provider: Optional[Provider] = None):
        existing_match = self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id
        ).first()
        preserve_existing_match = preferred_provider is not None and item.status == ItemStatus.MATCHED and existing_match is not None
        previous_status = item.status

        scrapers_to_try = self._build_scrapers_to_try(preferred_provider)
        logger.info('[adult:%s] Resolving %s | file=%s | oshash=%s | phash=%s', mode.value, item.id, item.filename, (item.hash_oshash or '')[:12], (item.hash_phash or '')[:12])
        logger.info('[adult:%s] Providers to try: %s', mode.value, [provider.value for _scraper, provider in scrapers_to_try])

        if not scrapers_to_try:
            logger.warning('No adult metadata provider API key configured.')
            item.status = previous_status if preserve_existing_match else ItemStatus.NO_MATCH
            self.db.flush()
            return

        for scraper, provider in scrapers_to_try:
            scene_data = None
            matched_hash_type = None
            hash_status = None

            if provider in (Provider.STASHDB, Provider.FANSDB):
                hash_query = """
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
                for hash_type, hash_value in [('oshash', item.hash_oshash), ('phash', item.hash_phash)]:
                    if scene_data or not hash_value:
                        continue
                    logger.info('[adult:%s] Trying %s %s lookup for %s', mode.value, provider.value, hash_type.upper(), item.filename)
                    cache_key = f'{provider.value}/hash/v4/{hash_type}/{hash_value}'
                    cached = scraper.cache.get(provider, cache_key)
                    if cached is not None:
                        if cached and cached.get("scene"):
                            scene_data = cached["scene"]
                            matched_hash_type = hash_type
                            hash_status = self._validate_hash_match(item, scene_data, ItemStatus(cached["status"]))
                        continue
                    try:
                        res = scraper.execute_query(hash_query, {'hash': hash_value})
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
                            
                            status = self._validate_hash_match(item, candidate, status)
                            if status:
                                scene_data = candidate
                                matched_hash_type = hash_type
                                hash_status = status
                                scraper.cache.set(provider, cache_key, {"scene": candidate, "status": status.value})
                            else:
                                scraper.cache.set(provider, cache_key, {})
                        else:
                            scraper.cache.set(provider, cache_key, {})
                    except Exception as exc:
                        logger.error('%s %s hash query failed: %s', provider.value, hash_type.upper(), exc)
            elif provider == Provider.PORNDB:
                api_token = scraper.get_setting('porndb_api_key') or scraper.get_setting('porndb_api_token')
                headers = {
                    'Authorization': f'Bearer {api_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
                for hash_type, hash_value in [('oshash', item.hash_oshash)]:
                    if scene_data or not hash_value:
                        continue
                    cache_key = f'porndb/scenes/hash/v4/{hash_type.lower()}/{hash_value}'
                    cached = scraper.cache.get(provider, cache_key)
                    if cached is not None:
                        if cached and cached.get("scene"):
                            scene_data = cached["scene"]
                            matched_hash_type = hash_type
                            hash_status = self._validate_hash_match(item, scene_data, ItemStatus(cached["status"]))
                        continue
                    url = f'{PORNDB_API_BASE}/scenes/hash/{hash_value}?type={hash_type.upper()}'
                    try:
                        resp = scraper.session.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
                        logger.info('[adult:%s] PornDB GET %s -> status %s', mode.value, url, resp.status_code)
                        if resp.status_code == 200:
                            res_json = resp.json()
                            candidate = (res_json or {}).get('data')
                            if candidate:
                                status = self._validate_hash_match(item, candidate, ItemStatus.MATCHED)
                                scene_data = candidate
                                matched_hash_type = hash_type
                                hash_status = status
                                scraper.cache.set(provider, cache_key, {"scene": candidate, "status": status.value})
                            else:
                                scraper.cache.set(provider, cache_key, {})
                        else:
                            scraper.cache.set(provider, cache_key, {})
                    except Exception as exc:
                        logger.error('PornDB %s query failed for scenes: %s', hash_type.upper(), exc)

            if scene_data and hash_status:
                logger.info('[adult:%s] Hash lookup matched %s -> provider=%s external_id=%s title=%s status=%s', mode.value, item.filename, provider.value, scene_data.get('id'), scene_data.get('title'), hash_status.value)
                self._persist_scene_match(
                    item=item,
                    provider=provider,
                    scraper=scraper,
                    scene_data=scene_data,
                    confidence=1.0,
                    status=hash_status,
                    media_item_id=item.id,
                )
                scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=f'hash: oshash={item.hash_oshash}, phash={item.hash_phash}',
                    result_count=1,
                    details={
                        'hash_match': True,
                        'hash_type': matched_hash_type,
                        'matched_scene_id': str(scene_data['id']),
                        'matched_title': scene_data.get('title'),
                        'final_status': hash_status.value,
                    },
                )
                self.db.flush()
                return

            search_queries = self._extract_scene_search_queries(item)
            logger.info('[adult:%s] Scene fallback queries for %s -> %s', mode.value, item.filename, search_queries)
            if not search_queries:
                continue

            all_candidates = []
            for search_title in search_queries:
                cache_key_search = f'{provider.value}/{mode.value}/search/v4/{search_title.strip().lower()}'
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
                    try:
                        res = scraper.execute_query(search_query, {'q': search_title})
                        scenes = res.get('searchScene', []) if res else []
                        scraper.cache.set(provider, cache_key_search, scenes or [])
                    except Exception as exc:
                        logger.error('Text query failed for provider %s: %s', provider.value, exc)
                        scenes = []

                for scene in scenes:
                    score = difflib.SequenceMatcher(None, normalize_title(search_title), normalize_title(scene.get('title') or '')).ratio()
                    if score >= 0.5:
                        all_candidates.append((score, scene, search_title, scenes))

            if not all_candidates:
                continue

            matched_candidates = []
            uncertain_candidates = []

            for score, scene, q, s in all_candidates:
                # Handle PornDB duration mappings (might be length or duration)
                s_duration = scene.get("duration") or scene.get("length")
                scene_sec = None
                if s_duration not in (None, ""):
                    try:
                        scene_sec = float(s_duration)
                    except (TypeError, ValueError):
                        pass

                if score >= 0.8:
                    if item.duration and scene_sec is not None:
                        diff = abs(float(item.duration) - scene_sec)
                        if diff <= 10:
                            matched_candidates.append((score, scene, q, s))
                        elif diff <= 120:
                            uncertain_candidates.append((score, scene, q, s))
                    else:
                        uncertain_candidates.append((score, scene, q, s))
                elif score >= 0.5:
                    if item.duration and scene_sec is not None:
                        diff = abs(float(item.duration) - scene_sec)
                        if diff <= 120:
                            uncertain_candidates.append((score, scene, q, s))

            # 1. Check matched candidates
            if matched_candidates:
                # If multiple matched candidates are found, but only one has matching duration (or if all have matching duration)
                # Since we already filtered by diff <= 10, they all have matched durations.
                if len(matched_candidates) == 1:
                    score, best_scene, best_query, best_scenes = matched_candidates[0]
                    self._persist_scene_match(
                        item=item,
                        provider=provider,
                        scraper=scraper,
                        scene_data=best_scene,
                        confidence=score,
                        status=ItemStatus.MATCHED,
                        media_item_id=item.id,
                    )
                    scraper.log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        search_query=best_query,
                        result_count=len(best_scenes),
                        details={
                            'hash_match': False,
                            'best_score': score,
                            'matched_scene_id': str(best_scene['id']),
                            'final_status': 'matched',
                        },
                    )
                    self.db.flush()
                    return
                else:
                    self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
                    seen_ids = set()
                    for score, scene, q, s in matched_candidates:
                        scene_id = scene.get("id")
                        if not scene_id or scene_id in seen_ids:
                            continue
                        seen_ids.add(scene_id)
                        self._persist_scene_match(
                            item=item,
                            provider=provider,
                            scraper=scraper,
                            scene_data=scene,
                            confidence=score,
                            is_active=False,
                            clear_existing=False,
                            status=ItemStatus.MULTIPLE,
                            media_item_id=item.id,
                        )
                    scraper.log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        search_query=matched_candidates[0][2],
                        result_count=len(matched_candidates[0][3]),
                        details={
                            'hash_match': False,
                            'best_score': matched_candidates[0][0],
                            'candidate_count': len(matched_candidates),
                            'matched_scene_ids': list(seen_ids),
                            'final_status': 'multiple',
                        },
                    )
                    self.db.flush()
                    return

            # 2. Check uncertain candidates
            if uncertain_candidates:
                if len(uncertain_candidates) == 1:
                    score, best_scene, best_query, best_scenes = uncertain_candidates[0]
                    self._persist_scene_match(
                        item=item,
                        provider=provider,
                        scraper=scraper,
                        scene_data=best_scene,
                        confidence=score,
                        status=ItemStatus.UNCERTAIN,
                        media_item_id=item.id,
                    )
                    scraper.log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        search_query=best_query,
                        result_count=len(best_scenes),
                        details={
                            'hash_match': False,
                            'best_score': score,
                            'matched_scene_id': str(best_scene['id']),
                            'final_status': 'uncertain',
                        },
                    )
                    self.db.flush()
                    return
                else:
                    self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
                    seen_ids = set()
                    for score, scene, q, s in uncertain_candidates:
                        scene_id = scene.get("id")
                        if not scene_id or scene_id in seen_ids:
                            continue
                        seen_ids.add(scene_id)
                        self._persist_scene_match(
                            item=item,
                            provider=provider,
                            scraper=scraper,
                            scene_data=scene,
                            confidence=score,
                            is_active=False,
                            clear_existing=False,
                            status=ItemStatus.MULTIPLE,
                            media_item_id=item.id,
                        )
                    scraper.log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        search_query=uncertain_candidates[0][2],
                        result_count=len(uncertain_candidates[0][3]),
                        details={
                            'hash_match': False,
                            'best_score': uncertain_candidates[0][0],
                            'candidate_count': len(uncertain_candidates),
                            'matched_scene_ids': list(seen_ids),
                            'final_status': 'multiple',
                        },
                    )
                    self.db.flush()
                    return

        if preserve_existing_match:
            logger.info(
                '[adult:%s] No match for %s on preferred provider %s, keeping existing match',
                mode.value,
                item.filename,
                preferred_provider.value,
            )
            item.status = previous_status
        else:
            logger.info('[adult:%s] No match for %s after all providers', mode.value, item.filename)
            item.status = ItemStatus.NO_MATCH
        self.db.flush()
