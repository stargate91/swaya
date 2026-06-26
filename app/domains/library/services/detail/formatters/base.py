from typing import Optional, Any
from app.domains.media_assets.services.images import image_processing_service

class MovieDetailFormatter:
    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return image_processing_service.resolve_image_url(path, subfolder, size)

    def format(self, item_id: Any, db: Any, scrapers: Any, current_uid: Any) -> Any:
        raise NotImplementedError()
