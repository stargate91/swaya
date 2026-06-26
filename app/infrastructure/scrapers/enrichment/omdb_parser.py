import logging
from typing import Dict, Any

from app.domains.metadata.models import MetadataMatch

logger = logging.getLogger(__name__)

class OMDBEnrichmentParser:
    def __init__(self, enricher):
        self.enricher = enricher

    def fetch_and_update_ratings(self, match: MetadataMatch, imdb_id: str):
        omdb_data = self.enricher._get_omdb_ratings_cached(imdb_id)
        if omdb_data:
            self.enricher.omdb.update_omdb_ratings(match, omdb_data)
