import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Coroutine
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from app.shared_kernel.enums import TaskStatus, TaskErrorCode
from app.domains.tasks.models import BackgroundTask
from app.shared_kernel.constants import DEFAULT_MAX_WORKERS

logger = logging.getLogger(__name__)

def map_exception_to_error_code(exc: Exception) -> TaskErrorCode:
    import requests
    
    exc_msg = str(exc).lower()
    if isinstance(exc, OperationalError) and "database is locked" in exc_msg:
        return TaskErrorCode.DATABASE_LOCK
    
    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = getattr(exc.response, "status_code", None)
        if status_code == 429:
            return TaskErrorCode.RATE_LIMIT
        if status_code in (401, 403):
            return TaskErrorCode.API_KEY_MISSING
        return TaskErrorCode.NETWORK_ERROR
        
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return TaskErrorCode.NETWORK_ERROR
        
    if "api key" in exc_msg or "api_key" in exc_msg or "unauthorized" in exc_msg or "api token" in exc_msg:
        return TaskErrorCode.API_KEY_MISSING
        
    return TaskErrorCode.UNKNOWN

class TaskManager:
    """
    Centralized service to supervise, track, execute, and cancel long-running
    background tasks (e.g. scanning, scraping) with database persistence.
    """

    def __init__(self, session_factory: Callable[[], Session], max_workers: Optional[int] = None):
        self.session_factory = session_factory
        # Track active asyncio tasks: task_id -> asyncio.Task
        self._active_tasks: Dict[int, asyncio.Task] = {}
        self._active_task_names: Dict[int, str] = {}
        self._cancelled_tasks = set()
        
        if max_workers is None:
            logical = os.cpu_count() or 4
            max_workers = max(DEFAULT_MAX_WORKERS, logical * 2)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        from app.domains.tasks.worker import DownloadWorker
        self.download_worker = DownloadWorker()

        from app.application.people.enrich_worker import PeopleEnrichWorker
        self.people_enrich_worker = PeopleEnrichWorker(session_factory=self.session_factory, executor=self.executor)

    @contextmanager
    def transaction(self):
        """
        Unified transaction helper to avoid SQLite locks. 
        Rolls back on error, commits on success, and retries on locked databases.
        """
        db = self.session_factory()
        max_attempts = 5
        try:
            yield db
            for attempt in range(max_attempts):
                try:
                    db.commit()
                    break
                except OperationalError as e:
                    db.rollback()
                    if "locked" not in str(e).lower() or attempt == max_attempts - 1:
                        raise
                    time.sleep(0.1 * (attempt + 1))
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def is_cancelled(self, task_id: Optional[int]) -> bool:
        """Thread-safe check to see if a task has been cancelled/aborted."""
        if task_id is None:
            return False
        if task_id in self._cancelled_tasks:
            return True
        
        # Fallback check against database
        db = self.session_factory()
        try:
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task and task.status == TaskStatus.ABORTED:
                self._cancelled_tasks.add(task_id)
                return True
        finally:
            db.close()
        return False

    def create_task(self, name: str, user_id: Optional[int] = None) -> int:
        """Registers a new pending task in the database and returns its task_id."""
        db = self.session_factory()
        try:
            task = BackgroundTask(
                name=name,
                user_id=user_id,
                status=TaskStatus.PENDING,
                progress=0.0
            )
            db.add(task)
            db.commit()
            task_id = task.id
            logger.info(f"Registered background task: {name} (ID: {task_id})")
            return task_id
        finally:
            db.close()

    def start_task(self, task_id: int, coro_func: Callable[..., Coroutine[Any, Any, Any]], *args, timeout: Optional[float] = None, **kwargs) -> None:
        """Starts a registered task asynchronously, tracking its execution and status."""
        async def task_wrapper():
            db = self.session_factory()
            try:
                # Set status to RUNNING in database
                task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
                if task:
                    task.status = TaskStatus.RUNNING
                    db.commit()
                    self._active_task_names[task_id] = task.name

                # Execute original coroutine with timeout if specified
                if timeout is not None:
                    await asyncio.wait_for(coro_func(task_id, *args, **kwargs), timeout=timeout)
                else:
                    await coro_func(task_id, *args, **kwargs)

                # Set status to COMPLETED
                task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
                if task and task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100.0
                    db.commit()
                logger.info(f"Task {task_id} completed successfully.")
            except (asyncio.CancelledError, asyncio.TimeoutError) as e:
                task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
                if task:
                    task.status = TaskStatus.ABORTED
                    if isinstance(e, asyncio.TimeoutError):
                        task.error_code = TaskErrorCode.UNKNOWN
                        task.error_message = "Task execution timed out."
                    db.commit()
                self._cancelled_tasks.add(task_id)
                logger.info(f"Task {task_id} was cancelled or timed out.")
            except Exception as e:
                logger.error(f"Task {task_id} failed with error: {e}", exc_info=True)
                task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_code = map_exception_to_error_code(e)
                    task.error_message = str(e)
                    db.commit()
            finally:
                db.close()
                self._active_tasks.pop(task_id, None)
                self._active_task_names.pop(task_id, None)

        # Create and track the asyncio task
        try:
            loop = asyncio.get_running_loop()
            async_task = loop.create_task(task_wrapper())
            self._active_tasks[task_id] = async_task
        except RuntimeError:
            # Fallback if no running loop (e.g. synchronous test context)
            import threading
            def run_sync():
                asyncio.run(task_wrapper())
            t = threading.Thread(target=run_sync)
            t.start()

    def update_progress(self, task_id: int, progress: float) -> None:
        """Updates the progress percentage (0.0 - 100.0) of a running task in the database with throttling."""
        if not hasattr(self, "_last_progress_update"):
            self._last_progress_update = {}
            
        now = time.time()
        last_time, last_prog = self._last_progress_update.get(task_id, (0.0, -1.0))
        
        # Throttle updates: only update if progress moved by >= 1% or >= 1.0 second elapsed,
        # but always allow 0% and 100% updates.
        if progress > 0.0 and progress < 100.0:
            if abs(progress - last_prog) < 1.0 and (now - last_time) < 1.0:
                return
                
        self._last_progress_update[task_id] = (now, progress)
        
        try:
            with self.transaction() as db:
                task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
                if task and task.status == TaskStatus.RUNNING:
                    task.progress = max(0.0, min(100.0, progress))
                    task.updated_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.warning(f"Failed to update progress for task {task_id}: {e}")

    def cancel_task(self, task_id: int) -> bool:
        """Cancels a running task. Returns True if task was running and got cancelled."""
        self._cancelled_tasks.add(task_id)
        async_task = self._active_tasks.get(task_id)
        if async_task and not async_task.done():
            async_task.cancel()
            return True
        
        # If not active in memory but still running in database, update status to CANCELLED
        db = self.session_factory()
        try:
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.ABORTED
                task.updated_at = datetime.now(timezone.utc)
                db.commit()
                return True
        finally:
            db.close()
            
        return False

    def get_task_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Returns details of a specific task."""
        db = self.session_factory()
        try:
            task = db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()
            if not task:
                return None
            return {
                "id": task.id,
                "name": task.name,
                "status": task.status.value,
                "progress": task.progress,
                "error_code": task.error_code.value if task.error_code else None,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            }
        finally:
            db.close()

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists active and historical background tasks."""
        db = self.session_factory()
        try:
            tasks = db.query(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status.value,
                    "progress": t.progress,
                    "error_code": t.error_code.value if t.error_code else None,
                    "error_message": t.error_message,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat()
                }
                for t in tasks
            ]
        finally:
            db.close()

    def has_active_heavy_tasks(self) -> bool:
        """Returns True if there is a running scan, rename, or undo task."""
        for task_id, task_name in list(self._active_task_names.items()):
            active_task = self._active_tasks.get(task_id)
            if active_task and not active_task.done():
                name_lower = task_name.lower()
                if "scan" in name_lower or "rename" in name_lower or "undo" in name_lower:
                    return True
        return False
