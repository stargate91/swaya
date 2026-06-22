from typing import Optional

from app.domains.library.models import MediaItem
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.enums import ItemStatus, ScanMode
from app.infrastructure.scrapers.enrichment.metadata_enricher import MetadataEnricher
from app.infrastructure.scrapers.resolver import Resolver


class BaseScanResolutionPipeline:
    def __init__(self, db_session, *, mode: ScanMode, include_adult: Optional[bool] = None, provider: Optional[str] = None):
        self.db = db_session
        self.mode = mode
        self.include_adult = include_adult
        self.provider = provider
        self.resolver = Resolver(db_session)

    def resolve_and_enrich(
        self,
        item: MediaItem,
        *,
        primary_language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: Optional[str] = None,
        task_id: Optional[int] = None,
        stop_requested=None,
    ):
        self.resolver.resolve_item(
            item,
            mode=self.mode,
            language=primary_language,
            task_id=task_id,
            include_adult=self.include_adult,
            provider=self.provider,
        )

        if stop_requested and stop_requested():
            return

        self.resolver.propagate_match(item)

        if item.status != ItemStatus.MATCHED:
            return

        self.enrich_matched_item(
            item,
            primary_language=primary_language,
            fallback_language=fallback_language,
            task_id=task_id,
            stop_requested=stop_requested,
        )

        if not item.group_hash:
            return

        siblings = self.db.query(MediaItem).filter(
            MediaItem.group_hash == item.group_hash,
            MediaItem.id != item.id,
            MediaItem.status == ItemStatus.MATCHED,
        ).all()
        for sibling in siblings:
            if stop_requested and stop_requested():
                return
            self.enrich_matched_item(
                sibling,
                primary_language=primary_language,
                fallback_language=fallback_language,
                task_id=task_id,
                stop_requested=stop_requested,
            )

    def enrich_matched_item(
        self,
        item: MediaItem,
        *,
        primary_language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: Optional[str] = None,
        task_id: Optional[int] = None,
        stop_requested=None,
    ):
        raise NotImplementedError


class MainstreamScanResolutionPipeline(BaseScanResolutionPipeline):
    def enrich_matched_item(
        self,
        item: MediaItem,
        *,
        primary_language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: Optional[str] = None,
        task_id: Optional[int] = None,
        stop_requested=None,
    ):
        enricher = MetadataEnricher(self.db)
        enricher.enrich_matched_item(
            item,
            language=primary_language,
            fallback_language=fallback_language,
        )


class ScenesScanResolutionPipeline(BaseScanResolutionPipeline):
    def enrich_matched_item(
        self,
        item: MediaItem,
        *,
        primary_language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: Optional[str] = None,
        task_id: Optional[int] = None,
        stop_requested=None,
    ):
        return


class PornDbMovieScanResolutionPipeline(MainstreamScanResolutionPipeline):
    pass


def get_scan_resolution_pipeline(db_session, mode: ScanMode = ScanMode.MOVIES_TV, include_adult: Optional[bool] = None, provider: Optional[str] = None):
    if mode == ScanMode.SCENES:
        return ScenesScanResolutionPipeline(db_session, mode=mode, include_adult=include_adult, provider=provider)
    if mode == ScanMode.PORNDB_MOVIE:
        return PornDbMovieScanResolutionPipeline(db_session, mode=mode, include_adult=include_adult, provider=provider)
    # If the provider is explicitly set to porndb in MOVIES_TV mode, we can route it through the adult movie pipeline.
    # But wait, PornDbMovieScanResolutionPipeline inherits from MainstreamScanResolutionPipeline so we can use that,
    # and we pass the provider to the resolver below.
    return MainstreamScanResolutionPipeline(db_session, mode=mode, include_adult=include_adult, provider=provider)
