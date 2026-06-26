import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional
from sqlalchemy.orm import Session

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.infrastructure.scrapers.resolver import normalize_title

logger = logging.getLogger(__name__)

class MatchPersister:
    def __init__(self, db: Session, api: Any, log_search_fn: Any, title_matcher: Any, candidate_scorer: Any):
        self.db = db
        self.api = api
        self.log_search = log_search_fn
        self.title_matcher = title_matcher
        self.candidate_scorer = candidate_scorer

    def save_matches(self, item: MediaItem, candidates: Dict[int, Dict[str, Any]], language: str, task_id: Optional[int] = None):
        """Persists candidates to database matches and updates item status."""
        self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
        self.db.flush()
        
        if not candidates:
            item.status = ItemStatus.NO_MATCH
            item.planned_path = None
            self.db.flush()
            self.log_search(
                task_id=task_id,
                media_item_id=item.id,
                provider=Provider.TMDB,
                search_query=item.filename,
                result_count=0,
                details={"candidates": [], "final_status": "no_match"}
            )
            return

        parsed = item.parsed_info or {}
        fn_data = parsed.get("fn") or {}
        it_data = parsed.get("it") or {}
        fd_data = parsed.get("fd") or {}

        target_year = fn_data.get("year") or fd_data.get("year") or it_data.get("year")
        parsed_title = fn_data.get("title") or fd_data.get("title") or it_data.get("title")
        
        details_cache: Dict[int, Dict[str, Any]] = {}
        candidate_titles_cache: Dict[int, Set[str]] = {}
        title_rank_cache: Dict[int, tuple[int, str]] = {}

        def get_candidate_details(tmdb_id: int, item_type: MediaType):
            if tmdb_id not in details_cache:
                details_cache[tmdb_id] = self.api.get_details(
                    tmdb_id,
                    "tv" if item_type == MediaType.TV else "movie",
                    language=language,
                )
            return details_cache[tmdb_id]

        def get_candidate_titles(candidate: Dict[str, Any], item_type: MediaType) -> Set[str]:
            tmdb_id = candidate.get("id")
            if not tmdb_id:
                return set()
            if tmdb_id not in candidate_titles_cache:
                candidate_titles_cache[tmdb_id] = self.title_matcher.collect_candidate_titles(
                    candidate,
                    get_candidate_details(tmdb_id, item_type),
                )
            return candidate_titles_cache[tmdb_id]

        def get_title_rank_and_best_title(candidate: Dict[str, Any], item_type: MediaType) -> tuple[int, str]:
            tmdb_id = candidate.get("id")
            if not tmdb_id:
                return 0, parsed_title
            if tmdb_id not in title_rank_cache:
                max_rank = 0
                best_t = parsed_title
                candidate_titles = get_candidate_titles(candidate, item_type)
                for t in [fn_data.get("title"), fd_data.get("title"), it_data.get("title")]:
                    if t:
                        rank = self.title_matcher.title_match_rank(t, candidate_titles)
                        if rank > max_rank:
                            max_rank = rank
                            best_t = t
                title_rank_cache[tmdb_id] = (max_rank, best_t)
            return title_rank_cache[tmdb_id]

        def get_candidate_score(x):
            source_priority = x.get("_source_priority", 0)
            date_str = x.get("release_date") or x.get("first_air_date")
            year_match = 0
            raw_type = x.get("item_type") or x.get("media_type", "movie")
            candidate_type = MediaType.TV if raw_type == "tv" else MediaType.MOVIE
            title_rank, best_title = get_title_rank_and_best_title(x, candidate_type)
            noise_penalty = self.candidate_scorer.candidate_noise_penalty(best_title, get_candidate_titles(x, candidate_type))
            if target_year and date_str:
                try:
                    c_year = int(date_str.split("-")[0])
                    if abs(c_year - target_year) <= 1:
                        year_match = 1
                except:
                    pass
            return (title_rank, source_priority, year_match, -noise_penalty)

        sorted_candidates = sorted(candidates.values(), key=get_candidate_score, reverse=True)
        limited_candidates = sorted_candidates[:15]
        match_count = len(limited_candidates)
        
        top_candidate_score = get_candidate_score(limited_candidates[0]) if limited_candidates else None
        top_score_candidates = 0
        if top_candidate_score:
            top_score_candidates = sum(
                1 for candidate in limited_candidates if get_candidate_score(candidate) == top_candidate_score
            )

        for i, data in enumerate(limited_candidates):
            tmdb_id = data.get("id")
            date_str = data.get("release_date") or data.get("first_air_date")
            release_date = None
            if date_str:
                try:
                    release_date = datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    pass

            raw_type = data.get("item_type") or data.get("media_type", "movie")
            itype = MediaType.TV if raw_type == "tv" else MediaType.MOVIE
            
            s_num = fn_data.get("season") or fd_data.get("season") or it_data.get("season")
            ep_num = fn_data.get("episode") or fd_data.get("episode") or it_data.get("episode")

            match = MetadataMatch(
                media_item_id=item.id,
                provider=Provider.TMDB,
                external_id=str(tmdb_id),
                media_type=itype,
                season_number=s_num,
                episode_number=ep_num,
                release_date=release_date,
                confidence_score=1.0,
                rating_tmdb=data.get("vote_average"),
                vote_count_tmdb=data.get("vote_count"),
                backdrop_path=data.get("backdrop_path")
            )
            
            if i == 0:
                match_year = release_date.year if release_date else None
                source_priority = data.get("_source_priority", 0)
                has_season = s_num is not None
                has_episode_num = ep_num is not None
                
                is_exact_title, _ = get_title_rank_and_best_title(data, itype)
                is_exact_title = is_exact_title >= 3
                cleaned_parsed = normalize_title(parsed_title)

                ambiguous_exact_candidates = 0
                if cleaned_parsed and target_year:
                    for candidate in limited_candidates:
                        if candidate.get("_source_priority", 0) != source_priority:
                            continue
                        candidate_raw_type = candidate.get("item_type") or candidate.get("media_type", "movie")
                        candidate_item_type = MediaType.TV if candidate_raw_type == "tv" else MediaType.MOVIE
                        rank, _ = get_title_rank_and_best_title(candidate, candidate_item_type)
                        if rank < 3:
                            continue
                        candidate_date = candidate.get("release_date") or candidate.get("first_air_date")
                        if not candidate_date:
                            continue
                        try:
                            candidate_year = int(str(candidate_date).split("-")[0])
                        except:
                            continue
                        if abs(candidate_year - target_year) <= 1:
                            ambiguous_exact_candidates += 1
                
                if itype == MediaType.TV and (not has_season or not has_episode_num):
                    item.status = ItemStatus.UNCERTAIN
                    item.planned_path = None
                elif source_priority <= 10 and match_count > 1:
                    item.status = ItemStatus.MULTIPLE
                    item.planned_path = None
                elif itype == MediaType.MOVIE and top_score_candidates > 1:
                    item.status = ItemStatus.MULTIPLE
                    item.planned_path = None
                elif ambiguous_exact_candidates > 1:
                    item.status = ItemStatus.MULTIPLE
                    item.planned_path = None
                elif is_exact_title and (itype != MediaType.TV or (has_season and has_episode_num)):
                    item.status = ItemStatus.MATCHED
                elif target_year and match_year and abs(target_year - match_year) <= 1:
                    item.status = ItemStatus.MATCHED
                elif target_year and match_year and abs(target_year - match_year) > 1:
                    item.status = ItemStatus.UNCERTAIN
                    item.planned_path = None
                elif not target_year and match_count > 1:
                    item.status = ItemStatus.MULTIPLE
                    item.planned_path = None
                else:
                    item.status = ItemStatus.MATCHED

            match.is_active = (i == 0 and item.status != ItemStatus.MULTIPLE)
            
            self.db.add(match)
            self.db.flush()

            # Create localized match text
            self.db.query(MetadataLocalization).filter(
                MetadataLocalization.match_id == match.id,
                MetadataLocalization.locale == language
            ).delete()

            loc = MetadataLocalization(
                match_id=match.id,
                locale=language,
                title=data.get("title") or data.get("name"),
                overview=data.get("overview"),
                poster_path=data.get("poster_path")
            )
            self.db.add(loc)

        # Collect candidate logging info
        cand_logs = []
        for c in candidates.values():
            try:
                raw_type = c.get("item_type") or c.get("media_type", "movie")
                ctype = MediaType.TV if raw_type == "tv" else MediaType.MOVIE
                score = get_candidate_score(c)
                trank, _ = get_title_rank_and_best_title(c, ctype)
            except Exception:
                score = None
                trank = None
            cand_logs.append({
                "id": c.get("id"),
                "title": c.get("title") or c.get("name"),
                "score": score,
                "title_rank": trank,
                "release_date": c.get("release_date") or c.get("first_air_date")
            })

        self.log_search(
            task_id=task_id,
            media_item_id=item.id,
            provider=Provider.TMDB,
            search_query=parsed_title or item.filename,
            result_count=len(candidates),
            details={
                "candidates": cand_logs,
                "final_status": item.status.value if item.status else None
            }
        )

        self.db.flush()
