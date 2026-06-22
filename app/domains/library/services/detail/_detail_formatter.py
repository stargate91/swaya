from typing import Optional
from app.domains.media_assets.services.images import ImageProcessingService

class DetailFormatter:
    def __init__(self):
        self.img_service = ImageProcessingService()

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        if not path:
            return None
        return self.img_service.resolve_image_url(path, subfolder, size)
