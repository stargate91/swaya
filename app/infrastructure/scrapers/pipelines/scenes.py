from typing import Optional

from app.domains.library.models import MediaItem
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.infrastructure.scrapers.pipelines.base import BaseResolverPipeline


class SceneAutoResolverPipeline(BaseResolverPipeline):
    def __init__(self, adult_resolver):
        self.adult = adult_resolver

    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        self.adult.resolve_primary_scene_item(item, task_id)


class StashDbSceneResolverPipeline(BaseResolverPipeline):
    def __init__(self, adult_resolver):
        self.adult = adult_resolver

    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        self.adult.resolve_stashdb_scene_item(item, task_id)


class FansDbSceneResolverPipeline(BaseResolverPipeline):
    def __init__(self, adult_resolver):
        self.adult = adult_resolver

    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        self.adult.resolve_fansdb_scene_item(item, task_id)


class PornDbSceneResolverPipeline(BaseResolverPipeline):
    def __init__(self, adult_resolver):
        self.adult = adult_resolver

    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        self.adult.resolve_porndb_scene_item(item, task_id)
