from app.infrastructure.scrapers.enrichment.parsers.movie_parser import enrich_movie
from app.infrastructure.scrapers.enrichment.parsers.tv_parser import enrich_tv
from app.infrastructure.scrapers.enrichment.parsers.people_parser import process_people

__all__ = [
    "enrich_movie",
    "enrich_tv",
    "process_people",
]
