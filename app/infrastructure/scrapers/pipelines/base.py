from typing import Optional

from app.domains.library.models import MediaItem
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE


class BaseResolverPipeline:
    def resolve_item(
        self,
        item: MediaItem,
        *,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
    ):
        raise NotImplementedError
