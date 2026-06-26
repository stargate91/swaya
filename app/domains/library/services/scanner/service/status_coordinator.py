import asyncio
import logging
import threading
import time
from typing import Dict, Any

from app.shared_kernel.enums import TaskStatus
from app.domains.tasks.models import BackgroundTask

logger = logging.getLogger(__name__)

class StatusCoordinator:
    """
    Submodule to manage scan state locks, progress reporting, and task stopping.
    """
    scan_status_lock = threading.Lock()
    scan_status = {
        "active": False,
        "phase": "idle",
        "current": 0,
        "total": 0,
        "start_time": 0,
        "can_stop": False,
        "stop_requested": False,
        "current_file_progress": 0.0,
        "last_completed": 0,
    }

    def __init__(self, db, task_manager):
        self.db = db
        self.task_manager = task_manager

    def get_scan_status(self) -> Dict[str, Any]:
        with StatusCoordinator.scan_status_lock:
            return StatusCoordinator.scan_status.copy()

    def get_hydrate_status(self) -> Dict[str, Any]:
        task = self.db.query(BackgroundTask).filter(
            BackgroundTask.name == "People Enrichment",
            BackgroundTask.status == TaskStatus.RUNNING
        ).order_by(BackgroundTask.id.desc()).first()
        
        if task:
            return {
                "active": True,
                "phase": "enriching",
                "current": int(task.progress),
                "total": 100
            }
        return {"active": False, "phase": "idle"}

    def get_image_status(self) -> Dict[str, Any]:
        worker = self.task_manager.download_worker
        queued = worker.queue.qsize()
        active_count = worker.active_downloads
        total = worker.batch_total
        completed = worker.completed_downloads
        pending = queued + active_count

        if worker.is_paused:
            return {
                "active": False,
                "deferred": pending > 0,
                "pending": pending,
                "total": total,
                "completed": completed,
                "progress": 0,
            }

        if pending == 0:
            return {
                "active": False,
                "pending": 0,
                "total": total,
                "completed": completed,
                "progress": 100 if total else 0
            }

        progress = (completed / total) * 100 if total > 0 else 0
        return {
            "active": True,
            "pending": pending,
            "total": total,
            "completed": completed,
            "progress": progress,
        }

    def reset_image_status(self) -> Dict[str, Any]:
        worker = self.task_manager.download_worker
        cleared = 0
        if hasattr(worker, "queue") and worker.queue:
            while not worker.queue.empty():
                try:
                    _, subfolder, filename = worker.queue.get_nowait()
                    worker._pending_downloads.discard((subfolder, filename))
                    worker.queue.task_done()
                    cleared += 1
                except (asyncio.QueueEmpty, ValueError):
                    break
        worker.batch_total = 0
        worker.completed_downloads = 0
        return {"status": "success", "message": f"Cleared {cleared} pending image tasks"}

    def is_stop_requested(self) -> bool:
        with StatusCoordinator.scan_status_lock:
            return StatusCoordinator.scan_status.get("stop_requested", False)

    def stop_active_task(self) -> Dict[str, Any]:
        stopped_any = False
        with StatusCoordinator.scan_status_lock:
            if StatusCoordinator.scan_status.get("active") and not StatusCoordinator.scan_status.get("stop_requested"):
                StatusCoordinator.scan_status["stop_requested"] = True
                stopped_any = True
                
        image_status = self.get_image_status()
        if image_status.get("active"):
            self.reset_image_status()
            stopped_any = True
            
        return {"status": "success", "message": "Stop requested" if stopped_any else "No active tasks to stop"}
