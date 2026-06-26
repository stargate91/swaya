from typing import Dict, Any

class MetadataSyncService:
    def get_sync_status(self) -> Dict[str, Any]:
        return {
            "active": False,
            "progress": 100,
            "phase": "idle",
            "status": "success"
        }

    def trigger_sync(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "status": "success",
            "message": "Metadata language sync completed successfully"
        }
