import logging
from typing import Optional
from app.shared_kernel.enums import Provider
from app.domains.metadata.models import MetadataMatch
from app.infrastructure.scrapers.support.base import BaseScraper

from app.shared_kernel.constants import OMDB_DEFAULT_ENDPOINT, OMDB_REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class OMDBScraper(BaseScraper):
    """OMDB-specific metadata retriever."""

    def __init__(self, db_session, cache_service=None):
        super().__init__(db_session, cache_service, Provider.OMDB)

    def fetch_omdb(self, imdb_id: str, force_refresh: bool = False) -> Optional[dict]:
        """Fetches additional ratings/details from OMDB (always SFW and non-localized)."""
        if not imdb_id or not imdb_id.startswith("tt"):
            return None

        api_key = self.get_setting("omdb_api_key")
        if not api_key:
            logger.warning("OMDB API key not configured.")
            return None

        cache_key = f"omdb/{imdb_id}"
        cached_data = self.cache.get(Provider.OMDB, cache_key, force_refresh=force_refresh)
        if cached_data:
            if cached_data.get("cached_error"):
                return None
            return cached_data

        url = OMDB_DEFAULT_ENDPOINT
        params = {"apikey": api_key, "i": imdb_id}
        try:
            resp = self.session.get(url, params=params, timeout=OMDB_REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("Response") == "True":
                    self.cache.set(Provider.OMDB, cache_key, data, status_code=200, external_id=imdb_id)
                    return data
                else:
                    self.cache.set(Provider.OMDB, cache_key, {}, status_code=404, external_id=imdb_id)
                    return None
            else:
                self.cache.set(Provider.OMDB, cache_key, {}, status_code=resp.status_code, external_id=imdb_id)
                return None
        except Exception as e:
            logger.error(f"Error querying OMDB for {imdb_id}: {e}")
            return None

    def update_omdb_ratings(self, match: MetadataMatch, raw_data: dict) -> None:
        """Parses OMDB raw ratings and updates the MetadataMatch record."""
        if not raw_data:
            return

        try:
            imdb_rating = raw_data.get("imdbRating")
            if imdb_rating and imdb_rating != "N/A":
                match.rating_imdb = float(imdb_rating)
        except Exception as e:
            logger.debug(f"Failed to parse IMDb rating: {e}")

        try:
            imdb_votes = raw_data.get("imdbVotes")
            if imdb_votes and imdb_votes != "N/A":
                match.vote_count_imdb = int(imdb_votes.replace(",", ""))
        except Exception as e:
            logger.debug(f"Failed to parse IMDb vote count: {e}")

        try:
            metascore = raw_data.get("Metascore")
            if metascore and metascore != "N/A":
                match.rating_meta = int(metascore)
        except Exception as e:
            logger.debug(f"Failed to parse Metascore: {e}")

        # Extract Rotten Tomatoes rating
        for rating in raw_data.get("Ratings", []):
            if rating.get("Source") == "Rotten Tomatoes":
                match.rating_rotten = rating.get("Value")
                break
