import difflib
import logging
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.orm import Session

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.infrastructure.scrapers.resolver import normalize_title, normalize_title_words
from app.shared_kernel.enums import ItemStatus, MediaType, Provider, ScanMode

from app.shared_kernel.ports.scrapers import ScraperGatewayPort

from app.infrastructure.scrapers.resolvers.adult.stashdb_resolver import StashDbResolver
from app.infrastructure.scrapers.resolvers.adult.porndb_resolver import PornDbResolver
from app.infrastructure.scrapers.resolvers.adult.fansdb_resolver import FansDbResolver
from app.infrastructure.scrapers.resolvers.adult.scorer import validate_hash_match
from app.infrastructure.scrapers.resolvers.adult.persister import persist_scene_match

logger = logging.getLogger(__name__)

class AdultResolver:
    """Handles resolving adult scene items against StashDB, PornDB, and FansDB APIs."""

    def __init__(self, db_session: Session, scraper_gateway: Optional[ScraperGatewayPort] = None):
        self.db = db_session
        from app.infrastructure.repositories.db_scraper_log_repository import DbScraperLogRepository
        from app.infrastructure.scrapers.support.gateway import scraper_gateway as default_gateway
        self.scraper_gateway = scraper_gateway or default_gateway
        self.scraper_log_repo = DbScraperLogRepository(db_session)

    def _log_search(self, task_id: Optional[int], media_item_id: Optional[int], provider: Provider, search_query: str, result_count: int, details: dict) -> None:
        self.scraper_log_repo.log_search(
            task_id=task_id,
            media_item_id=media_item_id,
            provider=provider,
            search_query=search_query,
            result_count=result_count,
            details=details
        )

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
        stash_scraper = self.scraper_gateway.adult(Provider.STASHDB, self.db)
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
        stash_scraper = self.scraper_gateway.adult(Provider.STASHDB, self.db)
        porndb_scraper = self.scraper_gateway.adult(Provider.PORNDB, self.db)
        fans_scraper = self.scraper_gateway.adult(Provider.FANSDB, self.db)

        resolvers = {
            Provider.STASHDB: (StashDbResolver(stash_scraper), Provider.STASHDB),
            Provider.PORNDB: (PornDbResolver(porndb_scraper), Provider.PORNDB),
            Provider.FANSDB: (FansDbResolver(fans_scraper), Provider.FANSDB),
        }

        available = {}
        for provider, (res_obj, _) in resolvers.items():
            if res_obj.is_configured():
                available[provider] = (res_obj, provider)

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
        return persist_scene_match(
            self.db,
            item=item,
            provider=provider,
            scraper=scraper,
            scene_data=scene_data,
            confidence=confidence,
            is_active=is_active,
            clear_existing=clear_existing,
            status=status,
            media_item_id=media_item_id
        )

    def _validate_hash_match(self, item: MediaItem, candidate: dict, current_status: ItemStatus) -> ItemStatus:
        return validate_hash_match(item, candidate, current_status)

    def _resolve_adult_item(self, item: MediaItem, mode: ScanMode = ScanMode.SCENES, task_id: Optional[int] = None, preferred_provider: Optional[Provider] = None):
        existing_match = self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id
        ).first()
        preserve_existing_match = preferred_provider is not None and item.status == ItemStatus.MATCHED and existing_match is not None
        previous_status = item.status

        scrapers_to_try = self._build_scrapers_to_try(preferred_provider)
        logger.info('[adult:%s] Resolving %s | file=%s | oshash=%s | phash=%s', mode.value, item.id, item.filename, (item.hash_oshash or '')[:12], (item.hash_phash or '')[:12])
        logger.info('[adult:%s] Providers to try: %s', mode.value, [provider.value for _resolver, provider in scrapers_to_try])

        if not scrapers_to_try:
            logger.warning('No adult metadata provider API key configured.')
            item.status = previous_status if preserve_existing_match else ItemStatus.NO_MATCH
            self.db.flush()
            return

        for resolver, provider in scrapers_to_try:
            scene_data = None
            matched_hash_type = None
            hash_status = None

            if provider in (Provider.STASHDB, Provider.FANSDB):
                for hash_type, hash_value in [('oshash', item.hash_oshash), ('phash', item.hash_phash)]:
                    if scene_data or not hash_value:
                        continue
                    logger.info('[adult:%s] Trying %s %s lookup for %s', mode.value, provider.value, hash_type.upper(), item.filename)
                    scene_data, hash_status = resolver.resolve_by_hash(item, hash_type, hash_value, self._validate_hash_match)
                    if scene_data:
                        matched_hash_type = hash_type
            elif provider == Provider.PORNDB:
                for hash_type, hash_value in [('oshash', item.hash_oshash)]:
                    if scene_data or not hash_value:
                        continue
                    scene_data, hash_status = resolver.resolve_by_hash(item, hash_type, hash_value, self._validate_hash_match)
                    if scene_data:
                        matched_hash_type = hash_type

            if scene_data and hash_status:
                logger.info('[adult:%s] Hash lookup matched %s -> provider=%s external_id=%s title=%s status=%s', mode.value, item.filename, provider.value, scene_data.get('id'), scene_data.get('title'), hash_status.value)
                self._persist_scene_match(
                    item=item,
                    provider=provider,
                    scraper=resolver.scraper,
                    scene_data=scene_data,
                    confidence=1.0,
                    status=hash_status,
                    media_item_id=item.id,
                )
                self._log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    provider=provider,
                    search_query=f'hash: oshash={item.hash_oshash}, phash={item.hash_phash}',
                    result_count=1,
                    details={
                        'hash_match': True,
                        'hash_type': matched_hash_type,
                        'matched_scene_id': str(scene_data['id']),
                        'final_status': hash_status.value if hash_status else None
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
                scenes = resolver.search_by_text(search_title)
                for scene in scenes:
                    score = difflib.SequenceMatcher(None, normalize_title(search_title), normalize_title(scene.get('title') or '')).ratio()
                    if score >= 0.5:
                        all_candidates.append((score, scene, search_title, scenes))

            if not all_candidates:
                continue

            matched_candidates = []
            uncertain_candidates = []

            for score, scene, q, s in all_candidates:
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
                if len(matched_candidates) == 1:
                    score, best_scene, best_query, best_scenes = matched_candidates[0]
                    self._persist_scene_match(
                        item=item,
                        provider=provider,
                        scraper=resolver.scraper,
                        scene_data=best_scene,
                        confidence=score,
                        status=ItemStatus.MATCHED,
                        media_item_id=item.id,
                    )
                    self._log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        provider=provider,
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
                            scraper=resolver.scraper,
                            scene_data=scene,
                            confidence=score,
                            is_active=False,
                            clear_existing=False,
                            status=ItemStatus.MULTIPLE,
                            media_item_id=item.id,
                        )
                    self._log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        provider=provider,
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
                        scraper=resolver.scraper,
                        scene_data=best_scene,
                        confidence=score,
                        status=ItemStatus.UNCERTAIN,
                        media_item_id=item.id,
                    )
                    self._log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        provider=provider,
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
                            scraper=resolver.scraper,
                            scene_data=scene,
                            confidence=score,
                            is_active=False,
                            clear_existing=False,
                            status=ItemStatus.MULTIPLE,
                            media_item_id=item.id,
                        )
                    self._log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        provider=provider,
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
