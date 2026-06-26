import logging
from sqlalchemy.orm import Session

from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.domains.library.services.detail._detail_formatter import DetailFormatter

# Import strategy formatters
from app.domains.library.services.detail.formatters.porndb_movie import PornDbMovieFormatter
from app.domains.library.services.detail.formatters.tmdb_movie import TmdbMovieFormatter
from app.domains.library.services.detail.formatters.local_movie import LocalMovieFormatter

logger = logging.getLogger(__name__)

class MovieDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers
        self.porndb_formatter = PornDbMovieFormatter()
        self.tmdb_formatter = TmdbMovieFormatter()
        self.local_formatter = LocalMovieFormatter()

    def get_library_item_detail(self, item_id: str, full_people: bool = False):
        from app.application.library.schemas import MovieDetailResponse
        from app.shared_kernel.user_context import get_current_user_id
        current_uid = get_current_user_id()

        # Tracked / External PornDB Movie Detail
        if isinstance(item_id, str) and item_id.startswith("porndb_"):
            return self.porndb_formatter.format(item_id, self.db, self.scrapers, current_uid)

        # Tracked / External TMDB Movie Detail
        if isinstance(item_id, str) and item_id.startswith("tmdb_"):
            return self.tmdb_formatter.format(item_id, self.db, self.scrapers, current_uid)

        # Local MediaItem Detail
        return self.local_formatter.format(item_id, self.db, self.scrapers, current_uid)
