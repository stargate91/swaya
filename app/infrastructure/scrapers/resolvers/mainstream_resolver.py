import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.domains.library.models import MediaItem
from app.shared_kernel.enums import Provider, ItemStatus
from app.domains.settings.models import SystemSetting, UserSetting
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.infrastructure.scrapers.resolvers.mainstream import (
    QuerySanitizer,
    TitleMatcher,
    CandidateScorer,
    MatchPersister,
)

logger = logging.getLogger(__name__)

class MainstreamResolver:
    """
    Scraper match resolver that scores and matches MediaItems to TMDB candidates.
    """

    def __init__(self, db_session: Session, scraper_gateway: Optional[ScraperGatewayPort] = None):
        self.db = db_session
        from app.infrastructure.repositories.db_scraper_log_repository import DbScraperLogRepository
        from app.infrastructure.scrapers.support.gateway import scraper_gateway as default_gateway
        self.scraper_gateway = scraper_gateway or default_gateway
        self.api = self.scraper_gateway.tmdb(db_session)
        self.scraper_log_repo = DbScraperLogRepository(db_session)

        # Helper instances
        self.sanitizer = QuerySanitizer()
        self.title_matcher = TitleMatcher()
        self.candidate_scorer = CandidateScorer(self.title_matcher)
        self.match_persister = MatchPersister(
            db=db_session,
            api=self.api,
            log_search_fn=self._log_search,
            title_matcher=self.title_matcher,
            candidate_scorer=self.candidate_scorer,
        )

    def _log_search(self, task_id: Optional[int], media_item_id: Optional[int], provider: Provider, search_query: str, result_count: int, details: dict) -> None:
        self.scraper_log_repo.log_search(
            task_id=task_id,
            media_item_id=media_item_id,
            provider=provider,
            search_query=search_query,
            result_count=result_count,
            details=details
        )

    def _sanitize_query(self, query: str) -> str:
        return self.sanitizer.sanitize_query(query)

    def _collect_candidate_titles(self, candidate: Dict[str, Any], details: Optional[Dict[str, Any]] = None) -> set:
        return self.title_matcher.collect_candidate_titles(candidate, details)

    def _title_match_rank(self, parsed_title: str, candidate_titles: set) -> int:
        return self.title_matcher.title_match_rank(parsed_title, candidate_titles)

    def _candidate_noise_penalty(self, parsed_title: str, candidate_titles: set) -> int:
        return self.candidate_scorer.candidate_noise_penalty(parsed_title, candidate_titles)

    def resolve_item(
        self,
        item: MediaItem,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
        include_adult: Optional[bool] = None,
    ):
        """Resolves MediaItem search candidates and populates matches."""
        candidates: Dict[int, Dict[str, Any]] = {}

        if include_adult is None:
            from app.shared_kernel.user_context import get_current_user_id
            current_user_id = get_current_user_id()
            include_adult_setting = self.db.query(UserSetting).filter(
                UserSetting.user_id == current_user_id,
                UserSetting.key == "include_adult",
            ).first()
            if not include_adult_setting:
                include_adult_setting = self.db.query(SystemSetting).filter(SystemSetting.key == "include_adult").first()
            include_adult = False
            if include_adult_setting and include_adult_setting.value:
                val = str(include_adult_setting.value).lower()
                include_adult = val == "true" or val == "1"

        parsed = item.parsed_info or {}
        fn_data = parsed.get("fn") or {}
        it_data = parsed.get("it") or {}
        fd_data = parsed.get("fd") or {}

        fn_season = fn_data.get("season")
        fd_season = fd_data.get("season")
        it_season = it_data.get("season")

        def filter_by_season_support(tv_results: list) -> list:
            target_season = fn_season or fd_season or it_season
            if not target_season:
                return tv_results
            
            valid = []
            for res in tv_results:
                res_id = res.get("id")
                if not res_id:
                    continue
                details = self.api.get_details(res_id, "tv", language=language)
                if details:
                    num_seasons = details.get("number_of_seasons") or 0
                    if num_seasons >= target_season:
                        valid.append(res)
                else:
                    valid.append(res)
            return valid

        # 1. Resolve via local NFO IMDb ID
        if item.nfo_imdb_id:
            res = self.api.find_by_imdb(item.nfo_imdb_id, language=language)
            if res:
                tmdb_type = "tv" if res.get("item_type") == "tv" else "movie"
                details = None
                try:
                    details = self.api.get_details(res["id"], tmdb_type, language=language)
                except Exception:
                    pass
                candidate_titles = self._collect_candidate_titles(res, details)
                
                match_found = False
                for t in [fn_data.get("title"), it_data.get("title"), fd_data.get("title")]:
                    if t and self._title_match_rank(t, candidate_titles) > 0:
                        match_found = True
                        break
                
                if match_found:
                    if res.get("item_type") == "tv":
                        res_list = filter_by_season_support([res])
                        if res_list:
                            self._add_candidate(candidates, res, source_priority=100)
                    else:
                        self._add_candidate(candidates, res, source_priority=100)

        # 2. Resolve via Guessit Search fallback
        if not candidates:
            search_tasks = [
                ("fn", fn_data.get("title"), fn_data.get("year"), 30),
                ("fd", fd_data.get("title"), fd_data.get("year"), 20),
                ("it", it_data.get("title"), it_data.get("year"), 10)
            ]
            
            for _source, title, year, source_priority in search_tasks:
                if not title:
                    continue
                
                clean_title = self._sanitize_query(title)
                if not clean_title:
                    continue

                is_tv = (
                    fn_data.get("type") in ("episode", "tv") or 
                    fd_data.get("type") in ("episode", "tv") or 
                    it_data.get("type") in ("episode", "tv")
                )
                tmdb_type = "tv" if is_tv else "movie"
                results = self.api.search(clean_title, item_type=tmdb_type, year=year, language=language, include_adult=include_adult)
                if tmdb_type == "tv":
                    results = filter_by_season_support(results)
                
                if not results and year:
                    results = self.api.search(clean_title, item_type=tmdb_type, year=None, language=language, include_adult=include_adult)
                    if tmdb_type == "tv":
                        results = filter_by_season_support(results)
                
                for res in results:
                    res["item_type"] = tmdb_type
                    self._add_candidate(candidates, res, source_priority=source_priority)

        self.match_persister.save_matches(item, candidates, language, task_id)

    def _add_candidate(self, candidates: Dict[int, Dict[str, Any]], res: Dict[str, Any], source_priority: int = 0):
        tmdb_id = res.get("id")
        if not tmdb_id:
            return

        existing = candidates.get(tmdb_id)
        if not existing:
            candidate = dict(res)
            candidate["_source_priority"] = source_priority
            candidates[tmdb_id] = candidate
            return

        existing["_source_priority"] = max(existing.get("_source_priority", 0), source_priority)
