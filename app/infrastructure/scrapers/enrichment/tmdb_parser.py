import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.domains.metadata.models import MetadataMatch, MetadataLocalization, Studio
from app.shared_kernel.enums import Provider, MediaType
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.infrastructure.scrapers.enrichment.parsers import (
    enrich_movie,
    enrich_tv,
    process_people,
)

logger = logging.getLogger(__name__)

class TMDBEnrichmentParser:
    def __init__(self, enricher):
        self.enricher = enricher

    @property
    def db(self) -> Session:
        return self.enricher.db

    @property
    def metadata_repo(self):
        return self.enricher.metadata_repo

    @property
    def people_repo(self):
        return self.enricher.people_repo

    def enrich_movie(self, match: MetadataMatch, language: str, include_ratings: bool = True):
        return enrich_movie(self, match, language, include_ratings=include_ratings)

    def enrich_tv(self, match: MetadataMatch, language: str, include_ratings: bool = True):
        return enrich_tv(self, match, language, include_ratings=include_ratings)

    def process_people(self, match: MetadataMatch, details: Dict[str, Any]):
        return process_people(self, match, details)

    def update_match_common(self, match: MetadataMatch, details: Dict[str, Any], include_ratings: bool = True):
        runtimes = details.get("episode_run_time", [])
        match.runtime = details.get("runtime") or (runtimes[0] if runtimes else None)
        match.popularity = details.get("popularity")
        match.rating_tmdb = details.get("vote_average")
        match.vote_count_tmdb = details.get("vote_count")
        
        release_date = details.get("release_date") or details.get("first_air_date")
        if release_date:
            try:
                match.release_date = datetime.strptime(release_date, "%Y-%m-%d")
            except Exception:
                pass
        
        ext_ids = details.get("external_ids", {})
        imdb_id = ext_ids.get("imdb_id") or match.imdb_id
        match.imdb_id = imdb_id

        match.original_language = details.get("original_language")
        match.origin_country = details.get("origin_country")
        spoken = details.get("spoken_languages", [])
        if spoken:
            match.spoken_languages = [s["iso_639_1"] for s in spoken]

        # Studios mapping
        for comp in details.get("production_companies") or []:
            s_name = comp.get("name")
            if s_name:
                studio = self.metadata_repo.get_studio_by_name(s_name)
                if not studio:
                    studio = self.metadata_repo.create_studio(name=s_name, logo_path=comp.get("logo_path"))

                if studio.logo_path and not studio.logo_path.startswith("logos/"):
                    local_logo = self.enricher._queue_image(studio.logo_path, "logos", f"studio_{studio.name}")
                    if local_logo:
                        studio.logo_path = local_logo

                if studio not in match.studios:
                    match.studios.append(studio)

        # OMDb Ratings
        if include_ratings and imdb_id:
            omdb_data = self.enricher._get_omdb_ratings_cached(imdb_id)
            if omdb_data:
                self.enricher.omdb.update_omdb_ratings(match, omdb_data)

        # Cast/Crew processing
        self.process_people(match, details)

    def get_or_create_loc(self, match: MetadataMatch, language: str) -> MetadataLocalization:
        language = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        equivalent_localizations = [
            loc for loc in match.localizations
            if LanguageService.resolve_request_locale(Provider.TMDB, loc.locale) == language
        ]
        if equivalent_localizations:
            loc = next((item for item in equivalent_localizations if item.locale == language), equivalent_localizations[0])
            loc.locale = language
            for duplicate in equivalent_localizations:
                if duplicate is not loc:
                    match.localizations.remove(duplicate)
            return loc
        loc = self.metadata_repo.get_localization(match.id, language)
        if not loc:
            loc = self.metadata_repo.create_localization(match.id, language)
            if loc not in match.localizations:
                match.localizations.append(loc)
        return loc
