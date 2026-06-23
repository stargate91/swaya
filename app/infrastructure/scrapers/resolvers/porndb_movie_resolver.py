import difflib
import logging
from typing import Optional
import difflib

from sqlalchemy.orm import Session

from app.shared_kernel.enums import ItemStatus, MediaType, Provider
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer
from app.infrastructure.scrapers.providers.omdb import OMDBScraper
from app.infrastructure.scrapers.support.persistence import ScraperPersister
from app.infrastructure.scrapers.providers.porndb import PornDBScraper
from app.infrastructure.scrapers.resolver import normalize_title


logger = logging.getLogger(__name__)


class PornDBMovieResolver:
    """Resolves adult movies without mixing PornDB scene results into the profile."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.scraper = PornDBScraper(db_session)

    def is_available(self) -> bool:
        return bool(
            self.scraper.get_setting("porndb_api_key")
            or self.scraper.get_setting("porndb_api_token")
        )

    @staticmethod
    def _parsed_identity(item: MediaItem) -> tuple[bool, list[str], Optional[int]]:
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
        
        queries = []
        for data in (fn_data, fd_data, it_data):
            alt = data.get("alternative_title") or data.get("episode_title")
            if alt and alt not in queries:
                queries.append(alt)
        for data in (fn_data, fd_data, it_data):
            title = data.get("title")
            if title and title not in queries:
                queries.append(title)

        year = fn_data.get("year") or fd_data.get("year") or it_data.get("year")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        return is_tv, queries, year

    @staticmethod
    def _movie_runtime_seconds(movie: dict) -> Optional[float]:
        candidates = [movie.get("runtime"), movie.get("duration"), movie.get("length")]
        for value in candidates:
            if value in (None, ""):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric <= 0:
                continue
            # PornDB movie runtime is expected in minutes; treat larger values as already-seconds.
            return numeric if numeric >= 600 else numeric * 60.0
        return None

    def _resolve_hash_type(self, item: MediaItem, *, file_hash: Optional[str], hash_type: str, task_id: Optional[int]) -> bool:
        if not file_hash or not self.is_available():
            return False

        movie = self.scraper.find_movie_by_hash(file_hash, hash_type=hash_type)
        if not movie:
            return False

        status = ItemStatus.MATCHED
        item_duration = float(item.duration) if item.duration not in (None, "") else None
        movie_duration = self._movie_runtime_seconds(movie)
        
        if hash_type == "PHASH":
            if item_duration and movie_duration:
                diff_ratio = abs(item_duration - movie_duration) / max(item_duration, movie_duration, 1.0)
                if diff_ratio <= 0.03:
                    status = ItemStatus.MATCHED
                elif diff_ratio <= 0.10:
                    status = ItemStatus.UNCERTAIN
                else:
                    logger.info('[movie] PHASH matched but duration diff ratio too high: %s', diff_ratio)
                    return False

        self._persist(item, movie, status=status, confidence=1.0)
        self.scraper.log_search(
            task_id=task_id,
            media_item_id=item.id,
            search_query=f"movie hash: {hash_type.lower()}={file_hash}",
            result_count=1,
            details={
                "hash_match": True,
                "hash_type": hash_type,
                "matched_movie_id": str(movie.get("id")),
                "matched_title": movie.get("title"),
                "final_status": status.value,
            },
        )
        return True

    def resolve_hash(self, item: MediaItem, task_id: Optional[int] = None) -> bool:
        is_tv, queries, year = self._parsed_identity(item)
        if is_tv or not self.is_available():
            return False

        if self._resolve_hash_type(item, file_hash=item.hash_oshash, hash_type="OSHASH", task_id=task_id):
            return True
        if self._resolve_hash_type(item, file_hash=item.hash_phash, hash_type="PHASH", task_id=task_id):
            return True
        return False

    def resolve_text(self, item: MediaItem, task_id: Optional[int] = None) -> bool:
        is_tv, queries, year = self._parsed_identity(item)
        if is_tv or not queries or not self.is_available():
            return False

        all_candidates = []
        for title in queries:
            movies = self.scraper.search_movies(title, year=year)
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
                    if year != candidate_year:
                        score -= 0.35
                    else:
                        score += 0.05

                all_candidates.append((max(0.0, min(score, 1.0)), movie, title, movies))

        if not all_candidates:
            self.scraper.log_search(
                task_id=task_id,
                media_item_id=item.id,
                search_query=", ".join(queries),
                result_count=0,
                details={
                    "hash_match": False,
                    "entity_type": "movie",
                    "final_status": "no_match",
                },
            )
            return False

        matched_candidates = []
        uncertain_candidates = []

        item_duration = float(item.duration) if item.duration not in (None, "") else None

        for score, movie, q, s in all_candidates:
            movie_duration = self._movie_runtime_seconds(movie)
            
            if score >= 0.8:
                if item_duration and movie_duration:
                    diff_ratio = abs(item_duration - movie_duration) / max(item_duration, movie_duration, 1.0)
                    if diff_ratio <= 0.03:
                        matched_candidates.append((score, movie, q, s))
                    elif diff_ratio <= 0.10:
                        uncertain_candidates.append((score, movie, q, s))
                else:
                    uncertain_candidates.append((score, movie, q, s))
            elif score >= 0.6:
                if item_duration and movie_duration:
                    diff_ratio = abs(item_duration - movie_duration) / max(item_duration, movie_duration, 1.0)
                    if diff_ratio <= 0.10:
                        uncertain_candidates.append((score, movie, q, s))

        # 1. Check matched candidates
        if matched_candidates:
            if len(matched_candidates) == 1:
                score, movie, q, s = matched_candidates[0]
                movie = self.scraper.enrich_movie_ratings(movie)
                self._persist(item, movie, status=ItemStatus.MATCHED, confidence=score)
                self.scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=q,
                    result_count=len(s),
                    details={
                        "hash_match": False,
                        "entity_type": "movie",
                        "best_score": score,
                        "matched_movie_id": str(movie.get("id")),
                        "matched_title": movie.get("title"),
                        "final_status": "matched",
                    },
                )
                return True
            else:
                self._persist_multiple(item, [m for _, m, _, _ in matched_candidates])
                self.scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=matched_candidates[0][2],
                    result_count=len(matched_candidates[0][3]),
                    details={
                        "hash_match": False,
                        "entity_type": "movie",
                        "best_score": matched_candidates[0][0],
                        "candidate_count": len(matched_candidates),
                        "matched_movie_ids": [str(m.get("id")) for _, m, _, _ in matched_candidates],
                        "final_status": "multiple",
                    },
                )
                return True

        # 2. Check uncertain candidates
        if uncertain_candidates:
            if len(uncertain_candidates) == 1:
                score, movie, q, s = uncertain_candidates[0]
                movie = self.scraper.enrich_movie_ratings(movie)
                self._persist(item, movie, status=ItemStatus.UNCERTAIN, confidence=score)
                self.scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=q,
                    result_count=len(s),
                    details={
                        "hash_match": False,
                        "entity_type": "movie",
                        "best_score": score,
                        "matched_movie_id": str(movie.get("id")),
                        "matched_title": movie.get("title"),
                        "final_status": "uncertain",
                    },
                )
                return True
            else:
                self._persist_multiple(item, [m for _, m, _, _ in uncertain_candidates])
                self.scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=uncertain_candidates[0][2],
                    result_count=len(uncertain_candidates[0][3]),
                    details={
                        "hash_match": False,
                        "entity_type": "movie",
                        "best_score": uncertain_candidates[0][0],
                        "candidate_count": len(uncertain_candidates),
                        "matched_movie_ids": [str(m.get("id")) for _, m, _, _ in uncertain_candidates],
                        "final_status": "multiple",
                    },
                )
                return True

        self.scraper.log_search(
            task_id=task_id,
            media_item_id=item.id,
            search_query=", ".join(queries),
            result_count=len(all_candidates),
            details={
                "hash_match": False,
                "entity_type": "movie",
                "final_status": "no_match",
            },
        )
        return False

    def _persist_multiple(self, item: MediaItem, movies: list[dict]) -> None:
        self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id
        ).delete()

        persisted_any = False
        seen_ids = set()
        for movie in movies:
            movie_id = movie.get("id")
            if not movie_id or movie_id in seen_ids:
                continue
            seen_ids.add(movie_id)
            enriched_movie = self.scraper.enrich_movie_ratings(movie)
            self._persist(
                item,
                enriched_movie,
                status=ItemStatus.MULTIPLE,
                confidence=1.0,
                is_active=False,
                clear_existing=False,
                flush=False,
            )
            persisted_any = True

        item.status = ItemStatus.MULTIPLE if persisted_any else ItemStatus.NO_MATCH
        self.db.flush()

    def _persist(
        self,
        item: MediaItem,
        movie: dict,
        *,
        status: ItemStatus = ItemStatus.MATCHED,
        confidence: float = 1.0,
        is_active: bool = True,
        clear_existing: bool = True,
        flush: bool = True,
    ) -> None:
        movie_id = movie.get("id")
        if not movie_id:
            return

        if clear_existing:
            self.db.query(MetadataMatch).filter(
                MetadataMatch.media_item_id == item.id
            ).delete()

        normalized = ScraperNormalizer.normalize_porndb_movie(movie)
        match = ScraperPersister(self.db).persist_normalized_scene(
            Provider.PORNDB,
            str(movie_id),
            normalized,
            media_type=MediaType.MOVIE,
            media_item_id=item.id,
        )
        match.is_active = is_active
        match.confidence_score = confidence
        if match.imdb_id:
            omdb = OMDBScraper(self.db)
            omdb_data = omdb.fetch_omdb(match.imdb_id)
            if omdb_data:
                omdb.update_omdb_ratings(match, omdb_data)
        item.status = status
        if flush:
            self.db.flush()
