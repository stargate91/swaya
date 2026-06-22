from typing import Optional

from app.domains.library.models import MediaItem
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.infrastructure.scrapers.pipelines.base import BaseResolverPipeline


class TmdbOmdbResolverPipeline(BaseResolverPipeline):
    def __init__(self, mainstream_resolver, include_adult: bool):
        self.mainstream = mainstream_resolver
        self.include_adult = include_adult

    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        self.mainstream.resolve_item(
            item,
            language,
            task_id,
            include_adult=self.include_adult,
        )
