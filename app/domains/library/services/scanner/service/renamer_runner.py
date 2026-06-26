import asyncio
import logging
import time
from typing import List, Optional, Dict, Any

from app.domains.history.models import ActionBatch
from app.domains.library.services.scanner.service.status_coordinator import StatusCoordinator

logger = logging.getLogger(__name__)

class RenamerRunner:
    """
    Submodule to manage item renames, previews, execution batches, and undo operations.
    """
    def __init__(self, service):
        self.service = service

    @property
    def db(self):
        return self.service.db

    @property
    def task_manager(self):
        return self.service.task_manager

    @property
    def library_port(self):
        return self.service.library_port

    def start_rename(self, item_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        with StatusCoordinator.scan_status_lock:
            if StatusCoordinator.scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {StatusCoordinator.scan_status.get('phase')}"}
                
        task_id = self.task_manager.create_task("Organize Items")
        self.task_manager.start_task(task_id, self._run_rename, item_ids)
        return {"status": "success", "message": "Organizing items in background"}

    async def _run_rename(self, task_id: int, item_ids: Optional[List[int]] = None):
        items = self.library_port.get_items_for_renaming(item_ids)

        if not items:
            with StatusCoordinator.scan_status_lock:
                StatusCoordinator.scan_status.update({
                    "active": False,
                    "phase": "idle",
                    "current": 0,
                    "total": 0,
                    "can_stop": False,
                    "stop_requested": False,
                    "current_file_progress": 0.0,
                    "last_completed": int(time.time()),
                })
            return

        batch = ActionBatch(name=f"Organize {len(items)} items")
        self.db.add(batch)
        self.db.commit()

        with StatusCoordinator.scan_status_lock:
            StatusCoordinator.scan_status.update({
                "active": True,
                "phase": "organizing",
                "current": 0,
                "total": len(items),
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
                "current_file_progress": 0.0,
            })

        from app.domains.library.services.renamer_engine import RenamerEngine
        from app.infrastructure.settings.formatter_config_adapter import build_formatter_from_db
        import os

        engine = RenamerEngine(self.db)
        formatter = build_formatter_from_db(self.db)

        previews = []
        for item in items:
            active_match = next((m for m in item.matches), None)
            if not active_match:
                continue
            dest_root = formatter.config.library_path if formatter.config.move_to_library and formatter.config.library_path else os.path.dirname(item.current_path)
            preview = formatter.plan_rename(active_match, dest_root)
            previews.append(preview)

        if previews:
            formatter.resolve_collisions(previews)

        with StatusCoordinator.scan_status_lock:
            StatusCoordinator.scan_status["total"] = len(previews)

        if not previews:
            self.db.commit()
            with StatusCoordinator.scan_status_lock:
                StatusCoordinator.scan_status.update({
                    "active": False,
                    "phase": "idle",
                    "current": 0,
                    "total": 0,
                    "can_stop": False,
                    "stop_requested": False,
                    "current_file_progress": 0.0,
                    "last_completed": int(time.time()),
                })
            return

        for idx, preview in enumerate(previews):
            if self.service._is_stop_requested():
                break

            def progress_cb(pct):
                with StatusCoordinator.scan_status_lock:
                    StatusCoordinator.scan_status["current_file_progress"] = pct

            await asyncio.to_thread(engine.execute_single, preview, batch.id, progress_callback=progress_cb)
            self.db.commit()

            with StatusCoordinator.scan_status_lock:
                StatusCoordinator.scan_status["current"] += 1
                StatusCoordinator.scan_status["current_file_progress"] = 0.0

            self.task_manager.update_progress(task_id, ((idx + 1) / len(previews)) * 100.0)

        self.db.commit()

        with StatusCoordinator.scan_status_lock:
            StatusCoordinator.scan_status["active"] = False
            StatusCoordinator.scan_status["phase"] = "idle"
            StatusCoordinator.scan_status["can_stop"] = False
            StatusCoordinator.scan_status["stop_requested"] = False
            StatusCoordinator.scan_status["current_file_progress"] = 0.0
            StatusCoordinator.scan_status["last_completed"] = int(time.time())

    def start_undo(self, batch_id: int) -> Dict[str, Any]:
        with StatusCoordinator.scan_status_lock:
            if StatusCoordinator.scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {StatusCoordinator.scan_status.get('phase')}"}
                
        task_id = self.task_manager.create_task(f"Undo batch {batch_id}")
        self.task_manager.start_task(task_id, self._run_undo, batch_id)
        return {"status": "success", "message": "Reverting batch in background"}

    async def _run_undo(self, task_id: int, batch_id: int):
        with StatusCoordinator.scan_status_lock:
            StatusCoordinator.scan_status.update({
                "active": True,
                "phase": "undoing",
                "current": 0,
                "total": 1,
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
            })
            
        from app.domains.library.services.renamer_engine import RenamerEngine
        engine = RenamerEngine(self.db)
        
        def progress_cb(current, total):
            with StatusCoordinator.scan_status_lock:
                StatusCoordinator.scan_status["current"] = current
                StatusCoordinator.scan_status["total"] = total
                
        await asyncio.to_thread(engine.undo_batch, batch_id, progress_callback=progress_cb, stop_check=self.service._is_stop_requested)
        
        with StatusCoordinator.scan_status_lock:
            StatusCoordinator.scan_status["active"] = False
            StatusCoordinator.scan_status["phase"] = "idle"
            StatusCoordinator.scan_status["can_stop"] = False
            StatusCoordinator.scan_status["stop_requested"] = False
