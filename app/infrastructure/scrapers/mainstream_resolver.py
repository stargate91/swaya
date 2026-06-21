import re
import difflib
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.settings.models import SystemSetting, UserSetting
from app.infrastructure.scrapers.tmdb import TMDBScraper
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

class MainstreamResolver:
    """
    Scraper match resolver that scores and matches MediaItems to TMDB candidates.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.api = TMDBScraper(db_session)

    def _sanitize_query(self, query: str) -> str:
        """Removes common patterns left behind by text parsing."""
        if not query:
            return ""
        
        clean_query = query
        # Remove season ranges (e.g. 1-4, Seasons 1-4, S1-S4)
        clean_query = re.sub(r'(?i)\b(?:seasons?|s)?\s*\d+\s*[-–]\s*(?:seasons?|s)?\s*\d+\b', "", clean_query)
        # Remove specific words
        for word in ["Mini", "Complete", "Season"]:
            clean_query = re.sub(rf"\b{word}\b", "", clean_query, flags=re.IGNORECASE)
            
        return " ".join(clean_query.split()).strip()

    def _collect_candidate_titles(self, candidate: Dict[str, Any], details: Optional[Dict[str, Any]] = None) -> Set[str]:
        titles: Set[str] = set()
        for key in ("title", "name", "original_title", "original_name"):
            value = candidate.get(key)
            if value:
                titles.add(str(value))

        if not details:
            return titles

        alt_titles_data = details.get("alternative_titles", {}).get("results", []) or details.get("alternative_titles", {}).get("titles", [])
        if isinstance(alt_titles_data, list):
            for alt in alt_titles_data:
                if isinstance(alt, dict):
                    for key in ("title", "name"):
                        value = alt.get(key)
                        if value:
                            titles.add(str(value))

        translations = details.get("translations", {}).get("translations", [])
        if isinstance(translations, list):
            for trans in translations:
                if isinstance(trans, dict):
                    t_data = trans.get("data", {}) or {}
                    for key in ("title", "name"):
                        value = t_data.get(key)
                        if value:
                            titles.add(str(value))

        return titles

    def _title_match_rank(self, parsed_title: str, candidate_titles: Set[str]) -> int:
        from app.infrastructure.scrapers.resolver import normalize_title, normalize_title_words
        normalized_query = normalize_title(parsed_title)
        normalized_query_words = normalize_title_words(parsed_title)
        if not normalized_query:
            return 0

        candidate_norms = {normalize_title(title) for title in candidate_titles if title}
        if normalized_query in candidate_norms:
            return 3

        candidate_word_norms = {normalize_title_words(title) for title in candidate_titles if title}
        if normalized_query_words and normalized_query_words in candidate_word_norms:
            return 2

        for title in candidate_titles:
            candidate_word_value = normalize_title_words(title)
            if normalized_query_words and candidate_word_value.startswith(f"{normalized_query_words} "):
                return 1

        for title in candidate_titles:
            if not title:
                continue
            normalized_candidate = normalize_title(title)
            if not normalized_candidate:
                continue
            if difflib.SequenceMatcher(None, normalized_query, normalized_candidate).ratio() >= 0.6:
                return 1

        return 0

    def _candidate_noise_penalty(self, parsed_title: str, candidate_titles: Set[str]) -> int:
        from app.infrastructure.scrapers.resolver import normalize_title_words
        if not candidate_titles:
            return 0

        parsed_words = normalize_title_words(parsed_title)
        combined_titles = " ".join(normalize_title_words(title) for title in candidate_titles if title)
        if not combined_titles:
            return 0

        if any(keyword in parsed_words for keyword in ("making of", "behind the scenes", "featurette", "special presentation", "documentary")):
            return 0

        noisy_keywords = (
            "making of",
            "behind the scenes",
            "featurette",
            "special presentation",
            "presentation",
            "documentary",
            "interview",
            "retrospective",
        )
        return 1 if any(keyword in combined_titles for keyword in noisy_keywords) else 0

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
            include_adult_setting = self.db.query(UserSetting).filter(
                UserSetting.user_id == 1,
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

        def filter_by_season_support(tv_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

        self._save_matches(item, candidates, language, task_id)

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

    def _save_matches(self, item: MediaItem, candidates: Dict[int, Dict[str, Any]], language: str, task_id: Optional[int] = None):
        """Persists candidates to database matches and updates item status."""
        self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
        

        self.db.flush()
        
        if not candidates:
            item.status = ItemStatus.NO_MATCH
            item.planned_path = None
            self.db.flush()
            self.api.log_search(
                task_id=task_id,
                media_item_id=item.id,
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
                candidate_titles_cache[tmdb_id] = self._collect_candidate_titles(
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
                        rank = self._title_match_rank(t, candidate_titles)
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
            noise_penalty = self._candidate_noise_penalty(best_title, get_candidate_titles(x, candidate_type))
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
                
                from app.infrastructure.scrapers.resolver import normalize_title
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

        self.api.log_search(
            task_id=task_id,
            media_item_id=item.id,
            search_query=parsed_title or item.filename,
            result_count=len(candidates),
            details={
                "candidates": cand_logs,
                "final_status": item.status.value if item.status else None
            }
        )

        self.db.flush()
