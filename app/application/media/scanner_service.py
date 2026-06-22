import asyncio
import logging
import threading
import time
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.domains.tasks import task_manager
from app.shared_kernel.enums import ActionStatus, ActionType, ItemStatus, MediaType, ScanMode
from app.domains.history.models import ActionBatch, ActionLog
from app.domains.library.models import MediaItem, Library, ExtraFile
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import Person

logger = logging.getLogger(__name__)

class ScannerService:
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

    def __init__(self, db: Session, scan_resolver_factory: Optional[Any] = None):
        self.db = db
        self.task_manager = task_manager
        self.scan_resolver_factory = scan_resolver_factory


    def get_scan_status(self) -> Dict[str, Any]:
        with ScannerService.scan_status_lock:
            return ScannerService.scan_status.copy()

    def get_hydrate_status(self) -> Dict[str, Any]:
        # Return status matching whether a "People Enrichment" task is running
        from app.domains.tasks.models import BackgroundTask
        from app.shared_kernel.enums import TaskStatus
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
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        with ScannerService.scan_status_lock:
            if ScannerService.scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {ScannerService.scan_status.get('phase')}"}
            
            ScannerService.scan_status.update({
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
        self.task_manager.start_task(task_id, self._run_scan, paths, stop_after, mode, include_adult, provider)
        return {"message": "Scan started in background", "paths": paths}

    async def _run_scan(
        self,
        task_id: int,
        paths: List[str],
        stop_after: Optional[str] = None,
        mode: Optional[Any] = None,
        include_adult: Optional[bool] = None,
        provider: Optional[str] = None,
    ):
        self.task_manager.download_worker.is_paused = True
        with ScannerService.scan_status_lock:
            ScannerService.scan_status.update({
                "active": True,
                "phase": "collecting",
                "current": 0,
                "total": 0,
                "start_time": time.time(),
                "can_stop": True,
                "stop_requested": False,
            })
            
        scan_mode = mode if mode is not None else ScanMode.MOVIES_TV
        logger.info("[scan:%s] Starting background scan | task_id=%s | paths=%s | include_adult=%s", scan_mode.value, task_id, paths, include_adult)
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
            
            logger.info("[scan:%s] Libraries selected: %s", scan_mode.value, [lib.root_path for lib in libraries_to_scan])

            for lib in libraries_to_scan:
                if self._is_stop_requested():
                    break
                def progress_cb(pct):
                    with ScannerService.scan_status_lock:
                        ScannerService.scan_status["current"] = int(pct * 100)
                        ScannerService.scan_status["total"] = 100
                    self.task_manager.update_progress(task_id, pct * 0.5)
                to_enrich, _ = await asyncio.to_thread(scanner.scan_library, lib.id, mode=scan_mode, progress_callback=progress_cb)
                logger.info("[scan:%s] Library %s produced %s items to enrich", scan_mode.value, lib.root_path, len(to_enrich))
                total_items_to_enrich.extend(to_enrich)

            # Phase 2: Metadata API Resolution
            logger.info("[scan:%s] Total items queued for resolver: %s", scan_mode.value, len(total_items_to_enrich))

            if total_items_to_enrich and not self._is_stop_requested():
                with ScannerService.scan_status_lock:
                    ScannerService.scan_status["phase"] = "resolving"
                    ScannerService.scan_status["current"] = 0
                    ScannerService.scan_status["total"] = len(total_items_to_enrich)
                    
                if self.scan_resolver_factory:
                    resolver = self.scan_resolver_factory(
                        self.db,
                        mode=scan_mode,
                        stop_checker=self._is_stop_requested,
                        include_adult=include_adult,
                        provider=provider,
                    )
                else:
                    raise RuntimeError("scan_resolver_factory is required but not provided")

                
                def resolve_progress_cb(current, total):
                    with ScannerService.scan_status_lock:
                        ScannerService.scan_status["current"] = current
                        ScannerService.scan_status["total"] = total
                    progress = 50.0 + (current / total) * 50.0
                    self.task_manager.update_progress(task_id, progress)
                    
                await asyncio.to_thread(resolver.resolve_all, total_items_to_enrich, progress_callback=resolve_progress_cb, task_id=task_id)
                logger.info("[scan:%s] Resolver phase finished for %s items", scan_mode.value, len(total_items_to_enrich))

            # Phase 3: People Enrichment (Run as separate background task to avoid deadlocks)
            if not self._is_stop_requested() and total_items_to_enrich:
                match_ids = []
                for item in total_items_to_enrich:
                    matches = self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).all()
                    match_ids.extend([m.id for m in matches])
                    
                if match_ids:
                    logger.info("[scan:%s] Queueing %s match ids for people enrichment", scan_mode.value, len(match_ids))
                    self.task_manager.people_enrich_worker.enqueue_enrich(match_ids)
                    
        except Exception as e:
            logger.error(f"Scan task failed: {e}", exc_info=True)
            raise e
        finally:
            logger.info("[scan:%s] Scan task finished", scan_mode.value)
            self.task_manager.download_worker.is_paused = False
            with ScannerService.scan_status_lock:
                ScannerService.scan_status["active"] = False
                ScannerService.scan_status["phase"] = "idle"
                ScannerService.scan_status["can_stop"] = False
                ScannerService.scan_status["stop_requested"] = False

    def _is_stop_requested(self) -> bool:
        with ScannerService.scan_status_lock:
            return ScannerService.scan_status.get("stop_requested", False)

    def stop_active_task(self) -> Dict[str, Any]:
        stopped_any = False
        with ScannerService.scan_status_lock:
            if ScannerService.scan_status.get("active") and not ScannerService.scan_status.get("stop_requested"):
                ScannerService.scan_status["stop_requested"] = True
                stopped_any = True
                
        # Also reset download queues
        image_status = self.get_image_status()
        if image_status.get("active"):
            self.reset_image_status()
            stopped_any = True
            
        return {"status": "success", "message": "Stop requested" if stopped_any else "No active tasks to stop"}

    def start_rename(self, item_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        with ScannerService.scan_status_lock:
            if ScannerService.scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {ScannerService.scan_status.get('phase')}"}
                
        # Register task in the DB task manager
        task_id = self.task_manager.create_task("Organize Items")
        
        # Run background job
        self.task_manager.start_task(task_id, self._run_rename, item_ids)
        return {"status": "success", "message": "Organizing items in background"}

    async def _run_rename(self, task_id: int, item_ids: Optional[List[int]] = None):
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
        
        with ScannerService.scan_status_lock:
            ScannerService.scan_status.update({
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
        
        # Pre-plan all previews to resolve collisions in batch
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

        for idx, preview in enumerate(previews):
            if self._is_stop_requested():
                break
                
            def progress_cb(pct):
                with ScannerService.scan_status_lock:
                    ScannerService.scan_status["current_file_progress"] = pct
                    
            success = await asyncio.to_thread(engine.execute_single, preview, batch.id, progress_callback=progress_cb)
            
            with ScannerService.scan_status_lock:
                ScannerService.scan_status["current"] += 1
                ScannerService.scan_status["current_file_progress"] = 0.0
                
            self.task_manager.update_progress(task_id, ((idx + 1) / len(previews)) * 100.0)
            
        with ScannerService.scan_status_lock:
            ScannerService.scan_status["active"] = False
            ScannerService.scan_status["phase"] = "idle"
            ScannerService.scan_status["can_stop"] = False
            ScannerService.scan_status["stop_requested"] = False

    def start_undo(self, batch_id: int) -> Dict[str, Any]:
        with ScannerService.scan_status_lock:
            if ScannerService.scan_status.get("active"):
                return {"status": "error", "message": f"Task already in progress: {ScannerService.scan_status.get('phase')}"}
                
        # Register task in the DB task manager
        task_id = self.task_manager.create_task(f"Undo batch {batch_id}")
        
        # Run background job
        self.task_manager.start_task(task_id, self._run_undo, batch_id)
        return {"status": "success", "message": "Reverting batch in background"}

    async def _run_undo(self, task_id: int, batch_id: int):
        with ScannerService.scan_status_lock:
            ScannerService.scan_status.update({
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
            with ScannerService.scan_status_lock:
                ScannerService.scan_status["current"] = current
                ScannerService.scan_status["total"] = total
                
        await asyncio.to_thread(engine.undo_batch, batch_id, progress_callback=progress_cb, stop_check=self._is_stop_requested)
        
        with ScannerService.scan_status_lock:
            ScannerService.scan_status["active"] = False
            ScannerService.scan_status["phase"] = "idle"
            ScannerService.scan_status["can_stop"] = False
            ScannerService.scan_status["stop_requested"] = False


