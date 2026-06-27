import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.ports.settings_port import SettingsPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.application.recommendations.schemas import RecommendationsResponse, ActionResponse
from app.domains.recommendations.services.recommendations_domain_service import RecommendationsDomainService
from app.domains.users.services.lists_service import ListsService as DomainListsService

logger = logging.getLogger(__name__)


class RecommendationsService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort, settings_port: Optional[SettingsPort] = None):
        self.db = db
        self.scraper = scrapers.tmdb(db)
        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
        self.settings = settings_port or DbSettingsAdapter(db)
        self.lists_service = DomainListsService(db)

    def _preferred_metadata_language(self) -> str:
        lang = self.settings.get_setting("primary_metadata_language")
        return lang if lang else DEFAULT_FALLBACK_LANGUAGE

    def get_recommendations(self, language: Optional[str] = None) -> RecommendationsResponse:
        watchlist_tmdb_ids = RecommendationsDomainService.fetch_watchlist_tmdb_ids(self.db)
        pref_lang = language or self._preferred_metadata_language()
        
        include_adult_val = self.settings.get_setting("include_adult")
        include_adult = str(include_adult_val).lower() == "true"

        trending_movie = self.scraper.get_trending("movie", "day", language=pref_lang)
        trending_tv = self.scraper.get_trending("tv", "day", language=pref_lang)

        trending_results = trending_movie.get("results", [])[:10] + trending_tv.get("results", [])[:10]
        if not include_adult:
            trending_results = [item for item in trending_results if not item.get("adult", False)]

        discover_movies = self.scraper.discover("movie", language=pref_lang, sort_by="popularity.desc", include_adult=include_adult).get("results", [])
        discover_tv = self.scraper.discover("tv", language=pref_lang, sort_by="popularity.desc", include_adult=include_adult).get("results", [])

        bindings = RecommendationsDomainService.resolve_local_recommendation_bindings(self.db, trending_results + discover_movies + discover_tv)

        def annotate(items):
            return RecommendationsDomainService.annotate_recommendations(items, bindings)

        return RecommendationsResponse(
            trending=annotate(trending_results),
            discover_movies=annotate(discover_movies),
            discover_tv=annotate(discover_tv),
            top_movie_genre="Action",
            top_tv_genre="Drama",
            watchlist_item_ids=watchlist_tmdb_ids
        )

    def add_to_watchlist(self, tmdb_id: int, media_type: str) -> ActionResponse:
        # Get watchlist ID
        lists = self.lists_service.get_all_lists()
        watchlist = next((l for l in lists if l.name == "Watchlist"), None)
        if not watchlist:
            return ActionResponse(status="error", message="Watchlist not found")
        
        item = self.lists_service.add_item_to_list(watchlist.id, tmdb_id=tmdb_id, media_type=media_type)
        return ActionResponse(status="success", id=item.id)

    def remove_from_watchlist(self, tmdb_id: int) -> ActionResponse:
        lists = self.lists_service.get_all_lists()
        watchlist = next((l for l in lists if l.name == "Watchlist"), None)
        if not watchlist:
            return ActionResponse(status="error", message="Watchlist not found")
        
        list_item_id = None
        for item in watchlist.items:
            if item.match and item.match.provider == Provider.TMDB and item.match.external_id == str(tmdb_id):
                list_item_id = item.id
                break
        
        if list_item_id is not None:
            self.lists_service.remove_item_from_list(watchlist.id, list_item_id)
            return ActionResponse(status="success")
            
        return ActionResponse(status="error", message="Item not found in watchlist")

# For Provider reference
from app.shared_kernel.enums import Provider
