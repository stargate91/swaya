from typing import Any, Optional

from app.shared_kernel.enums import MediaType, Provider
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.infrastructure.scrapers.fansdb import FansDBScraper
from app.infrastructure.scrapers.mainstream_enricher import MainstreamEnricher
from app.infrastructure.scrapers.normalizer import ScraperNormalizer
from app.infrastructure.scrapers.persistence import ScraperPersister
from app.infrastructure.scrapers.porndb import PornDBScraper
from app.infrastructure.scrapers.stashdb import StashDBScraper
from app.infrastructure.scrapers.tmdb import TMDBScraper


class InfrastructureScraperGateway(ScraperGatewayPort):
    def tmdb(self, db_session: Any) -> TMDBScraper:
        return TMDBScraper(db_session)

    def adult(self, provider: Provider, db_session: Any) -> Any:
        scrapers = {
            Provider.STASHDB: StashDBScraper,
            Provider.PORNDB: PornDBScraper,
            Provider.FANSDB: FansDBScraper,
        }
        scraper_type = scrapers.get(provider)
        if scraper_type is None:
            raise ValueError(f"Unsupported adult metadata provider: {provider}")
        return scraper_type(db_session)

    def enrich_mainstream(
        self,
        db_session: Any,
        item: Any,
        language: str,
        *,
        commit: bool = True,
    ) -> None:
        MainstreamEnricher(db_session).enrich_matched_item(
            item,
            language=language,
            commit=commit,
        )

    def normalize_adult_scene(self, provider: Provider, raw_data: dict) -> dict:
        return ScraperNormalizer.normalize_adult_scene(provider.value, raw_data)

    def persist_adult_scene(
        self,
        db_session: Any,
        provider: Provider,
        external_id: str,
        normalized: dict,
        *,
        media_type: Optional[MediaType] = None,
    ) -> Any:
        return ScraperPersister(db_session).persist_normalized_scene(
            provider,
            external_id,
            normalized,
            media_type=media_type or MediaType.SCENE,
        )


scraper_gateway = InfrastructureScraperGateway()