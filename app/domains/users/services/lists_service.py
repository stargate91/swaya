# Re-export from new location for backward compatibility
# ListsService has been moved to app.application.catalog.lists_service
from app.application.catalog.lists_service import ListsService

__all__ = ["ListsService"]
