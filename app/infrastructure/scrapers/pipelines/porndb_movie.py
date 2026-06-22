from typing import Optional

from app.domains.library.models import MediaItem
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.infrastructure.scrapers.pipelines.base import BaseResolverPipeline


class PornDbMovieResolverPipeline(BaseResolverPipeline):
    def __init__(self, porndb_movie_resolver):
        self.porndb_movies = porndb_movie_resolver

    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        if self.porndb_movies.resolve_hash(item, task_id):
            return
        self.porndb_movies.resolve_text(item, task_id)
