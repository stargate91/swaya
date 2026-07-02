import asyncio
import logging
import time
from typing import List, Optional, Dict, Any

from app.domains.history.models import ActionBatch
from app.domains.library.services.scanner.service.status_coordinator import StatusCoordinator

import os
from app.domains.library.services.renamer_engine import RenamerEngine
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

    @property
    def formatter_factory(self):
        return self.service.formatter_factory

    @property
    def move_with_progress_fn(self):
        return self.service.move_with_progress_fn

    @property
    def send_to_trash_fn(self):
        return self.service.send_to_trash_fn

    def start_rename(self, item_ids: Optional[List[int]] = None, organize_in_place: bool = False) -> Dict[str, Any]:
        with StatusCoordinator.scan_status_lock:
            if StatusCoordinator.scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {StatusCoordinator.scan_status.get('phase')}"}
                
        task_id = self.task_manager.create_task("Organize Items")
        self.task_manager.start_task(task_id, self._run_rename, item_ids, organize_in_place)
        return {"status": "success", "message": "Organizing items in background"}

    async def _run_rename(self, task_id: int, item_ids: Optional[List[int]] = None, organize_in_place: bool = False):
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

        batch_name_prefix = "Organize in Place" if organize_in_place else "Organize"
        batch = ActionBatch(name=f"{batch_name_prefix} {len(items)} items")
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

        formatter = self.formatter_factory(self.db) if self.formatter_factory else None
        engine = RenamerEngine(
            self.db,
            library_port=self.library_port,
            formatter=formatter,
            move_with_progress_fn=self.move_with_progress_fn,
            send_to_trash_fn=self.send_to_trash_fn
        )

        previews = []
        for item in items:
            active_match = next((m for m in item.matches), None)
            if not active_match:
                continue
            dest_root = formatter.config.library_path if formatter.config.move_to_library and formatter.config.library_path else os.path.dirname(item.current_path)
            preview = formatter.plan_rename(active_match, dest_root)
            previews.append(preview)

        if previews:
            if organize_in_place:
                for preview in previews:
                    m_item = next((it for it in items if it.id == preview.item_id), None)
                    if m_item:
                        preview.destination_root = os.path.dirname(m_item.current_path).replace("\\", "/")
                        preview.target_subpath = ""
                        preview.target_name = os.path.basename(m_item.current_path)
                    for extra_prev in preview.extra_previews:
                        extra_obj = self.library_port.get_extra_by_id(extra_prev.extra_id)
                        if extra_obj:
                            extra_prev.destination_root = os.path.dirname(extra_obj.current_path).replace("\\", "/")
                            extra_prev.target_subpath = ""
                            extra_prev.target_name = os.path.basename(extra_obj.current_path)
            else:
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
                smooth_pct = ((idx + pct) / len(previews)) * 100.0
                self.task_manager.update_progress(task_id, smooth_pct)

            await asyncio.to_thread(engine.execute_single, preview, batch.id, progress_callback=progress_cb, organize_in_place=organize_in_place)
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
            
        engine = RenamerEngine(
            self.db,
            library_port=self.library_port,
            move_with_progress_fn=self.move_with_progress_fn,
            send_to_trash_fn=self.send_to_trash_fn
        )
        
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
