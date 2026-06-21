import logging
from sqlalchemy.orm import Session
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class MetadataEnricher:
    """
    Dispatcher facade that delegates enrichment to MainstreamEnricher or AdultEnricher.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        from app.infrastructure.scrapers.mainstream_enricher import MainstreamEnricher
        self.mainstream = MainstreamEnricher(db_session)

    def enrich_matched_item(
        self,
        item: MediaItem,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: str = None,
        include_ratings: bool = True,
        commit: bool = True,
    ):
        """Fetches and stores complete metadata for the active match."""
        # Find active/first match for this media item
        active_match = self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id
        ).first()

        if not active_match:
            return

        if active_match.is_adult:
            # Adult scenes are fully resolved and enriched in one step during lookup
            return

        self.mainstream.enrich_matched_item(
            item,
            language=language,
            fallback_language=fallback_language,
            include_ratings=include_ratings,
            commit=commit
        )
