import difflib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.shared_kernel.enums import ItemStatus, MediaType, Provider
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.infrastructure.scrapers.normalizer import ScraperNormalizer
from app.infrastructure.scrapers.omdb import OMDBScraper
from app.infrastructure.scrapers.persistence import ScraperPersister
from app.infrastructure.scrapers.porndb import PornDBScraper
from app.infrastructure.scrapers.resolver import normalize_title


logger = logging.getLogger(__name__)


class PornDBMovieResolver:
    """Resolves adult movies without mixing PornDB scene/JAV results into the profile."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.scraper = PornDBScraper(db_session)

    def is_available(self) -> bool:
        return bool(
            self.scraper.get_setting("porndb_api_key")
            or self.scraper.get_setting("porndb_api_token")
        )

    @staticmethod
    def _parsed_identity(item: MediaItem) -> tuple[bool, Optional[str], Optional[int]]:
        parsed = item.parsed_info or {}
        fn_data = parsed.get("fn") or {}
        it_data = parsed.get("it") or {}
        fd_data = parsed.get("fd") or {}

        is_tv = any(
            data.get("type") in ("episode", "tv")
            or data.get("season") not in (None, "")
            or data.get("episode") not in (None, "")
            for data in (fn_data, it_data, fd_data)
        )
        title = fn_data.get("title") or fd_data.get("title") or it_data.get("title")
        year = fn_data.get("year") or fd_data.get("year") or it_data.get("year")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        return is_tv, title, year

    def resolve_hash(self, item: MediaItem, task_id: Optional[int] = None) -> bool:
        is_tv, _title, _year = self._parsed_identity(item)
        if is_tv or not item.hash_oshash or not self.is_available():
            return False

        movie = self.scraper.find_movie_by_hash(item.hash_oshash)
        if not movie:
            return False

        self._persist(item, movie)
        self.scraper.log_search(
            task_id=task_id,
            media_item_id=item.id,
            search_query=f"movie hash: oshash={item.hash_oshash}",
            result_count=1,
            details={
                "hash_match": True,
                "matched_movie_id": str(movie.get("id")),
                "matched_title": movie.get("title"),
                "final_status": "matched",
            },
        )
        return True

    def resolve_text(self, item: MediaItem, task_id: Optional[int] = None) -> bool:
        is_tv, title, year = self._parsed_identity(item)
        if is_tv or not title or not self.is_available():
            return False

        movies = self.scraper.search_movies(title, year=year)
        candidates = []
        normalized_query = normalize_title(title)
        for movie in movies:
            candidate_title = movie.get("title") or ""
            score = difflib.SequenceMatcher(
                None,
                normalized_query,
                normalize_title(candidate_title),
            ).ratio()

            candidate_date = movie.get("date")
            candidate_year = None
            if candidate_date:
                try:
                    candidate_year = int(str(candidate_date).split("-")[0])
                except (TypeError, ValueError):
                    pass
            if year and candidate_year:
                score += 0.05 if year == candidate_year else -0.1
            candidates.append((max(0.0, min(score, 1.0)), movie))

        candidates.sort(key=lambda entry: entry[0], reverse=True)
        if not candidates or candidates[0][0] < 0.82:
            self.scraper.log_search(
                task_id=task_id,
                media_item_id=item.id,
                search_query=title,
                result_count=len(candidates),
                details={
                    "hash_match": False,
                    "entity_type": "movie",
                    "best_score": candidates[0][0] if candidates else None,
                    "final_status": "no_match",
                },
            )
            return False

        best_score, movie = candidates[0]
        movie = self.scraper.enrich_movie_ratings(movie)
        self._persist(item, movie)
        self.scraper.log_search(
            task_id=task_id,
            media_item_id=item.id,
            search_query=title,
            result_count=len(candidates),
            details={
                "hash_match": False,
                "entity_type": "movie",
                "best_score": best_score,
                "matched_movie_id": str(movie.get("id")),
                "matched_title": movie.get("title"),
                "final_status": "matched",
            },
        )
        return True

    def _persist(self, item: MediaItem, movie: dict) -> None:
        movie_id = movie.get("id")
        if not movie_id:
            return

        self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id
        ).delete()
        self.db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.PORNDB,
            MetadataMatch.external_id == str(movie_id),
            MetadataMatch.media_type == MediaType.MOVIE,
        ).delete()

        normalized = ScraperNormalizer.normalize_porndb_movie(movie)
        match = ScraperPersister(self.db).persist_normalized_scene(
            Provider.PORNDB,
            str(movie_id),
            normalized,
            media_type=MediaType.MOVIE,
        )
        match.media_item_id = item.id
        if match.imdb_id:
            omdb = OMDBScraper(self.db)
            omdb_data = omdb.fetch_omdb(match.imdb_id)
            if omdb_data:
                omdb.update_omdb_ratings(match, omdb_data)
        item.status = ItemStatus.MATCHED
        self.db.flush()
