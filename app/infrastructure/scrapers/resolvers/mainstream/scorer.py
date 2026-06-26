import difflib
from typing import Set, Dict, Any, Optional
from app.infrastructure.scrapers.resolver import normalize_title, normalize_title_words

class TitleMatcher:
    def collect_candidate_titles(self, candidate: Dict[str, Any], details: Optional[Dict[str, Any]] = None) -> Set[str]:
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

    def title_match_rank(self, parsed_title: str, candidate_titles: Set[str]) -> int:
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

class CandidateScorer:
    def __init__(self, title_matcher: TitleMatcher):
        self.title_matcher = title_matcher

    def candidate_noise_penalty(self, parsed_title: str, candidate_titles: Set[str]) -> int:
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
