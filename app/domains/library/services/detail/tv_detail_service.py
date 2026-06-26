import logging
from sqlalchemy.orm import Session
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.domains.library.services.detail._detail_formatter import DetailFormatter

# Import strategy formatters
from app.domains.library.services.detail.formatters.tv_show import TvShowFormatter
from app.domains.library.services.detail.formatters.tv_season import TvSeasonFormatter

logger = logging.getLogger(__name__)

class TvDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers
        self.tmdb_scraper = scrapers.tmdb(db)
        self.show_formatter = TvShowFormatter()
        self.season_formatter = TvSeasonFormatter()

    def get_library_tv_detail(self, tv_tmdb_id: str, seasons_limit: int = 999, initial_episodes_limit: int = 999, language: str = None):
        return self.show_formatter.format(
            tv_tmdb_id=tv_tmdb_id,
            db=self.db,
            tmdb_scraper=self.tmdb_scraper,
            seasons_limit=seasons_limit,
            initial_episodes_limit=initial_episodes_limit,
            language=language
        )

    def get_library_tv_season_detail(self, tv_tmdb_id: str, season_number: int):
        return self.season_formatter.format(
            tv_tmdb_id=tv_tmdb_id,
            season_number=season_number,
            db=self.db,
            tmdb_scraper=self.tmdb_scraper
        )
