import asyncio
import logging
import threading
import time
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.tasks import task_manager
from app.core.enums import ActionStatus, ActionType, ItemStatus, MediaType, ScanMode
from app.domains.history.models import ActionBatch, ActionLog
from app.domains.media.models.filesystem import MediaItem, Library, ExtraFile
from app.domains.media.models.metadata import MetadataMatch
from app.domains.people.models import Person

logger = logging.getLogger(__name__)

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
}

class ScannerService:
    def __init__(self, db: Session):
        self.db = db
        self.task_manager = task_manager

    def get_scan_status(self) -> Dict[str, Any]:
        with scan_status_lock:
            return scan_status.copy()

    def get_hydrate_status(self) -> Dict[str, Any]:
        # Return status matching whether a "People Enrichment" task is running
        from app.core.tasks.models import BackgroundTask
        from app.core.enums import TaskStatus
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
            return {"active": False, "pending": 0, "total": total, "completed": completed, "progress": 100 if total else 0}

        progress = (completed / total) * 100 if total > 0 else 0
        return {
            "active": True,
            "pending": pending,
            "total": total,
            "completed": completed,
            "progress": progress,
        }

    def reset_image_status(self) -> Dict[str, Any]:
        # Reset image status by clearing the background queue
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

    def start_scan(
        self,
        paths: List[str],
        stop_after: Optional[str] = None,
        mode: Optional[Any] = None,
        include_adult: Optional[bool] = None,
    ) -> Dict[str, Any]:
        global scan_status
        with scan_status_lock:
            if scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {scan_status.get('phase')}"}
            
            scan_status.update({
                "active": True,
                "phase": "starting",
                "current": 0,
                "total": 0,
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
                "current_file_progress": 0.0,
            })
                
        # Register task in the new db task manager
        task_id = self.task_manager.create_task("Library Scan")
        
        # Run background job
        self.task_manager.start_task(task_id, self._run_scan, paths, stop_after, mode, include_adult)
        return {"message": "Scan started in background", "paths": paths}

    async def _run_scan(
        self,
        task_id: int,
        paths: List[str],
        stop_after: Optional[str] = None,
        mode: Optional[Any] = None,
        include_adult: Optional[bool] = None,
    ):
        global scan_status
        self.task_manager.download_worker.is_paused = True
        with scan_status_lock:
            scan_status.update({
                "active": True,
                "phase": "collecting",
                "current": 0,
                "total": 0,
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
            })
            
        scan_mode = mode if mode is not None else ScanMode.MOVIES_TV
        try:
            # Repair inconsistent items (status is matched/organized/renamed but has no matches)
            inconsistent_items = self.db.query(MediaItem).filter(
                MediaItem.status.in_([ItemStatus.MATCHED, ItemStatus.ORGANIZED, ItemStatus.RENAMED])
            ).all()
            repaired_count = 0
            for item in inconsistent_items:
                if not item.matches:
                    item.status = ItemStatus.NEW
                    repaired_count += 1
            if repaired_count > 0:
                self.db.commit()
                logger.info(f"Automatically repaired {repaired_count} inconsistent matched items by resetting status to NEW.")

            # Match libraries from DB with request paths
            libraries_to_scan = []
            all_libs = self.db.query(Library).all()
            
            import os
            for p in paths:
                norm_p = p.replace("\\", "/").rstrip("/")
                matched_lib = None
                for lib in all_libs:
                    lib_p = lib.root_path.replace("\\", "/").rstrip("/")
                    if lib_p == norm_p or norm_p.startswith(lib_p + "/") or lib_p.startswith(norm_p + "/"):
                        matched_lib = lib
                        break
                if matched_lib:
                    if matched_lib not in libraries_to_scan:
                        libraries_to_scan.append(matched_lib)
                else:
                    new_lib = Library(name=os.path.basename(p) or "Library", root_path=p)
                    self.db.add(new_lib)
                    libraries_to_scan.append(new_lib)

            if not libraries_to_scan:
                # If no paths were passed, fallback to all existing libraries
                libraries_to_scan = all_libs
            else:
                self.db.commit()

            total_items_to_enrich = []
            from app.application.media.scanner_manager import ScannerManager
            scanner = ScannerManager(self.db)
            
            for lib in libraries_to_scan:
                if self._is_stop_requested():
                    break
                def progress_cb(pct):
                    with scan_status_lock:
                        scan_status["current"] = int(pct * 100)
                        scan_status["total"] = 100
                    self.task_manager.update_progress(task_id, pct * 0.5)
                to_enrich, _ = await asyncio.to_thread(scanner.scan_library, lib.id, mode=scan_mode, progress_callback=progress_cb)
                total_items_to_enrich.extend(to_enrich)

            # Phase 2: Metadata API Resolution
            if total_items_to_enrich and not self._is_stop_requested():
                with scan_status_lock:
                    scan_status["phase"] = "resolving"
                    scan_status["current"] = 0
                    scan_status["total"] = len(total_items_to_enrich)
                    
                from app.infrastructure.scrapers.scan_resolver import ScanResolver
                resolver = ScanResolver(
                    self.db,
                    mode=scan_mode,
                    stop_checker=self._is_stop_requested,
                    include_adult=include_adult,
                )
                
                def resolve_progress_cb(current, total):
                    with scan_status_lock:
                        scan_status["current"] = current
                        scan_status["total"] = total
                    progress = 50.0 + (current / total) * 50.0
                    self.task_manager.update_progress(task_id, progress)
                    
                await asyncio.to_thread(resolver.resolve_all, total_items_to_enrich, progress_callback=resolve_progress_cb, task_id=task_id)

            # Phase 3: People Enrichment (Run as separate background task to avoid deadlocks)
            if not self._is_stop_requested() and total_items_to_enrich:
                match_ids = []
                for item in total_items_to_enrich:
                    matches = self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).all()
                    match_ids.extend([m.id for m in matches])
                    
                if match_ids:
                    self.task_manager.people_enrich_worker.enqueue_enrich(match_ids)
                    
        except Exception as e:
            logger.error(f"Scan task failed: {e}", exc_info=True)
            raise e
        finally:
            self.task_manager.download_worker.is_paused = False
            with scan_status_lock:
                scan_status["active"] = False
                scan_status["phase"] = "idle"
                scan_status["can_stop"] = False
                scan_status["stop_requested"] = False

    def _is_stop_requested(self) -> bool:
        with scan_status_lock:
            return scan_status.get("stop_requested", False)

    def stop_active_task(self) -> Dict[str, Any]:
        global scan_status
        stopped_any = False
        with scan_status_lock:
            if scan_status.get("active") and not scan_status.get("stop_requested"):
                scan_status["stop_requested"] = True
                stopped_any = True
                
        # Also reset download queues
        image_status = self.get_image_status()
        if image_status.get("active"):
            self.reset_image_status()
            stopped_any = True
            
        return {"status": "success", "message": "Stop requested" if stopped_any else "No active tasks to stop"}

    def start_rename(self, item_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        global scan_status
        with scan_status_lock:
            if scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {scan_status.get('phase')}"}
                
        # Register task in the DB task manager
        task_id = self.task_manager.create_task("Organize Items")
        
        # Run background job
        self.task_manager.start_task(task_id, self._run_rename, item_ids)
        return {"status": "success", "message": "Organizing items in background"}

    async def _run_rename(self, task_id: int, item_ids: Optional[List[int]] = None):
        global scan_status
        from sqlalchemy.orm import joinedload
        query = self.db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.extras),
            joinedload(MediaItem.overrides)
        ).filter(MediaItem.status == ItemStatus.MATCHED)
        if item_ids is not None:
            query = query.filter(MediaItem.id.in_(item_ids))
        items = query.all()
        
        if not items:
            return
            
        batch = ActionBatch(name=f"Organize {len(items)} items")
        self.db.add(batch)
        self.db.commit()
        
        with scan_status_lock:
            scan_status.update({
                "active": True,
                "phase": "organizing",
                "current": 0,
                "total": len(items),
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
            })
            
        from app.application.media.renamer_engine import RenamerEngine
        from app.infrastructure.settings.formatter_config_adapter import build_formatter_from_db
        import os
        
        engine = RenamerEngine(self.db)
        formatter = build_formatter_from_db(self.db)
        
        for idx, item in enumerate(items):
            if self._is_stop_requested():
                break
                
            active_match = next((m for m in item.matches), None)
            if not active_match:
                with scan_status_lock:
                    scan_status["current"] += 1
                continue
                
            dest_root = formatter.config.library_path if formatter.config.move_to_library and formatter.config.library_path else os.path.dirname(item.current_path)
            preview = formatter.plan_rename(active_match, dest_root)
            
            def progress_cb(pct):
                with scan_status_lock:
                    scan_status["current_file_progress"] = pct
                    
            success = await asyncio.to_thread(engine.execute_single, preview, batch.id, progress_callback=progress_cb)
            
            with scan_status_lock:
                scan_status["current"] += 1
                scan_status["current_file_progress"] = 0.0
                
            self.task_manager.update_progress(task_id, ((idx + 1) / len(items)) * 100.0)
            
        with scan_status_lock:
            scan_status["active"] = False
            scan_status["phase"] = "idle"
            scan_status["can_stop"] = False
            scan_status["stop_requested"] = False

    def start_undo(self, batch_id: int) -> Dict[str, Any]:
        global scan_status
        with scan_status_lock:
            if scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {scan_status.get('phase')}"}
                
        # Register task in the DB task manager
        task_id = self.task_manager.create_task(f"Undo batch {batch_id}")
        
        # Run background job
        self.task_manager.start_task(task_id, self._run_undo, batch_id)
        return {"status": "success", "message": "Reverting batch in background"}

    async def _run_undo(self, task_id: int, batch_id: int):
        global scan_status
        with scan_status_lock:
            scan_status.update({
                "active": True,
                "phase": "undoing",
                "current": 0,
                "total": 1,
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
            })
            
        from app.application.media.renamer_engine import RenamerEngine
        engine = RenamerEngine(self.db)
        
        def progress_cb(current, total):
            with scan_status_lock:
                scan_status["current"] = current
                scan_status["total"] = total
                
        await asyncio.to_thread(engine.undo_batch, batch_id, progress_callback=progress_cb, stop_check=self._is_stop_requested)
        
        with scan_status_lock:
            scan_status["active"] = False
            scan_status["phase"] = "idle"
            scan_status["can_stop"] = False
            scan_status["stop_requested"] = False

    def get_history(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        offset = (page - 1) * limit
        batches = self.db.query(ActionBatch).order_by(desc(ActionBatch.created_at)).offset(offset).limit(limit + 1).all()
        
        has_more = len(batches) > limit
        if has_more:
            batches = batches[:limit]
            
        result = []
        for b in batches:
            success_count = self.db.query(ActionLog).filter(
                ActionLog.batch_id == b.id,
                ActionLog.status == ActionStatus.SUCCESS
            ).count()
            
            failed_count = self.db.query(ActionLog).filter(
                ActionLog.batch_id == b.id,
                ActionLog.status == ActionStatus.FAILED
            ).count()
            
            undone_count = self.db.query(ActionLog).filter(
                ActionLog.batch_id == b.id,
                ActionLog.status == ActionStatus.UNDONE
            ).count()
            
            movie_count = self.db.query(ActionLog).join(MediaItem, ActionLog.media_item_id == MediaItem.id).filter(
                ActionLog.batch_id == b.id,
                ActionLog.status.in_([ActionStatus.SUCCESS, ActionStatus.UNDONE])
            ).filter(
                MediaItem.matches.any(MetadataMatch.media_type == MediaType.MOVIE)
            ).count()
            
            episode_count = self.db.query(ActionLog).join(MediaItem, ActionLog.media_item_id == MediaItem.id).filter(
                ActionLog.batch_id == b.id,
                ActionLog.status.in_([ActionStatus.SUCCESS, ActionStatus.UNDONE])
            ).filter(
                MediaItem.matches.any(MetadataMatch.media_type == MediaType.EPISODE)
            ).count()
            
            extra_count = self.db.query(ActionLog).filter(
                ActionLog.batch_id == b.id,
                ActionLog.status.in_([ActionStatus.SUCCESS, ActionStatus.UNDONE]),
                ActionLog.extra_file_id != None
            ).count()
            
            is_undone = (success_count == 0) and (undone_count > 0 or failed_count == 0)
            status = "undone" if is_undone else "completed" if failed_count == 0 else "partial"
            
            logs_query = self.db.query(ActionLog).filter(ActionLog.batch_id == b.id).all()
            logs_list = [{
                "id": log.id,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "status": log.status.value,
                "error_message": log.error_message
            } for log in logs_query]
            
            result.append({
                "id": b.id,
                "name": b.name or f"Batch #{b.id}",
                "created_at": b.created_at.isoformat() + "Z",
                "success_count": success_count + undone_count,
                "failed_count": failed_count,
                "movie_count": movie_count,
                "episode_count": episode_count,
                "extra_count": extra_count,
                "remaining_count": success_count,
                "undone_count": undone_count,
                "status": status,
                "logs": logs_list
            })
            
        return {
            "items": result,
            "page": page,
            "has_more": has_more
        }
