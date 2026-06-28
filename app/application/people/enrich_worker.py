import asyncio
import logging
from typing import List, Optional, Set

from app.domains.people.models import Person, MediaPersonLink
from app.domains.people.services.people_enricher import PeopleEnricher
from app.domains.tasks.models import BackgroundTask
from app.shared_kernel.enums import TaskStatus

logger = logging.getLogger(__name__)

class PeopleEnrichWorker:
    def __init__(self, session_factory=None, executor=None, concurrency: int = 4, scrapers=None, task_monitor=None, image_downloader=None):
        self.session_factory = session_factory
        self.executor = executor
        self.concurrency = concurrency
        self.scrapers = scrapers
        self.task_monitor = task_monitor
        self.image_downloader = image_downloader
        self._queue: Optional[asyncio.Queue] = None
        self.is_running = False
        self.active_task_id: Optional[int] = None
        self.total_queued = 0
        self.completed_count = 0
        self._worker_tasks = []
        self._pending_person_ids: Set[int] = set()

    @property
    def queue(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    async def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self.loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._worker_tasks = [
            asyncio.create_task(self._process_queue(i))
            for i in range(self.concurrency)
        ]
        logger.info(f"PeopleEnrichWorker started with {self.concurrency} workers.")

    async def stop(self) -> None:
        self.is_running = False
        for t in self._worker_tasks:
            t.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        logger.info("PeopleEnrichWorker stopped.")

    def enqueue_enrich(self, match_ids: List[int]) -> None:
        if not match_ids:
            return

        db = self.session_factory()
        try:
            links = db.query(MediaPersonLink).filter(MediaPersonLink.match_id.in_(match_ids)).all()
            person_ids = list(set(link.person_id for link in links))
        finally:
            db.close()

        if not person_ids:
            return

        if hasattr(self, "loop") and self.loop and self.loop.is_running():
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop == self.loop:
                self.loop.create_task(self._enqueue_items(person_ids))
            else:
                asyncio.run_coroutine_threadsafe(self._enqueue_items(person_ids), self.loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._enqueue_items(person_ids))
            except RuntimeError:
                asyncio.run(self._enqueue_items(person_ids))

    def enqueue_people(self, person_ids: List[int]) -> None:
        if not person_ids:
            return

        if hasattr(self, "loop") and self.loop and self.loop.is_running():
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop == self.loop:
                self.loop.create_task(self._enqueue_items(person_ids))
            else:
                asyncio.run_coroutine_threadsafe(self._enqueue_items(person_ids), self.loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._enqueue_items(person_ids))
            except RuntimeError:
                asyncio.run(self._enqueue_items(person_ids))

    async def _enqueue_items(self, person_ids: List[int]) -> None:
        if not self.is_running:
            await self.start()

        # Check if there is an active task
        db = self.session_factory()
        try:
            if self.active_task_id is not None:
                t = db.query(BackgroundTask).filter(BackgroundTask.id == self.active_task_id).first()
                if not t or t.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    self.active_task_id = None

            if self.active_task_id is None:
                task = BackgroundTask(
                    name="People Enrichment",
                    status=TaskStatus.RUNNING,
                    progress=0.0
                )
                db.add(task)
                db.commit()
                self.active_task_id = task.id
                self.total_queued = 0
                self.completed_count = 0
                self._pending_person_ids.clear()
        finally:
            db.close()

        new_to_queue = []
        for pid in person_ids:
            if pid not in self._pending_person_ids:
                self._pending_person_ids.add(pid)
                new_to_queue.append(pid)

        if new_to_queue:
            self.total_queued += len(new_to_queue)
            for pid in new_to_queue:
                await self.queue.put(pid)
            logger.info(f"Enqueued {len(new_to_queue)} people for enrichment. Total queue: {self.total_queued}")

    async def _process_queue(self, worker_id: int) -> None:
        while self.is_running:
            try:
                # Pause/wait if any heavy tasks (scan, rename, undo) are running
                while self.task_monitor and self.task_monitor.has_active_heavy_tasks():
                    await asyncio.sleep(2)

                person_id = await self.queue.get()
                
                # Check cancellation
                if self.active_task_id and self.task_monitor and self.task_monitor.is_cancelled(self.active_task_id):
                    self.queue.task_done()
                    continue

                try:
                    success = await asyncio.to_thread(self._enrich_single_person, person_id)
                except Exception as e:
                    logger.error(f"Worker-{worker_id} failed to enrich person {person_id}: {e}")
                    success = False

                self.completed_count += 1
                self._pending_person_ids.discard(person_id)

                # Update progress
                if self.active_task_id and self.task_monitor:
                    progress = (self.completed_count / self.total_queued) * 100.0 if self.total_queued > 0 else 100.0
                    self.task_monitor.update_progress(self.active_task_id, progress)

                    # If queue is empty and all done, complete the task
                    db = self.session_factory()
                    try:
                        if self.queue.empty() and not self._pending_person_ids:
                            task = db.query(BackgroundTask).filter(BackgroundTask.id == self.active_task_id).first()
                            if task and task.status == TaskStatus.RUNNING:
                                task.status = TaskStatus.COMPLETED
                                task.progress = 100.0
                                db.commit()
                                logger.info(f"People Enrichment task {self.active_task_id} completed.")
                                self.active_task_id = None
                    finally:
                        db.close()

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception in PeopleEnrichWorker loop-{worker_id}: {e}")
                await asyncio.sleep(2)

    def _enrich_single_person(self, person_id: int) -> bool:
        from app.domains.people.models import Person, ExternalSourceLink
        db = self.session_factory()
        try:
            person = db.query(Person).filter(Person.id == person_id).first()
            if not person:
                return False
            person_name = person.name
            links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
            link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
            external_ids = person.external_ids or {}
            is_adult = person.is_adult
        finally:
            db.close()

        enricher = PeopleEnricher(None, self.scrapers, session_factory=self.session_factory, task_monitor=self.task_monitor, image_downloader=self.image_downloader)
        fetched_data = enricher.fetch_external_details(person_name, external_ids, link_data, is_adult=is_adult)
        if not fetched_data:
            return False

        db = self.session_factory()
        try:
            person = db.query(Person).filter(Person.id == person_id).first()
            if person:
                enricher.db = db
                enricher.apply_enriched_data(person, fetched_data)
                db.commit()
                return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save enriched data for person ID {person_id}: {e}", exc_info=True)
        finally:
            db.close()
        return False
