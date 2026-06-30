import asyncio
import logging
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from app.domains.media_assets.services.images import image_processing_service, ImageProcessingService
from app.shared_kernel.constants import HEAVY_IMAGE_DOWNLOAD_TIMEOUT

if TYPE_CHECKING:
    from app.shared_kernel.ports.task_monitor_port import TaskMonitorPort

logger = logging.getLogger(__name__)

class DownloadWorker:
    """
    Background worker that monitors and handles downloading of external media assets
    (posters, backdrops, logos, stills, performer profile images).
    Utilizes ImageProcessingService to store files and generate correct thumbnails.
    Supports concurrent processing of downloads.
    """

    def __init__(self, image_service: Optional[ImageProcessingService] = None, concurrency: int = 6, task_monitor: Optional["TaskMonitorPort"] = None):
        self.image_service = image_service or image_processing_service
        self.task_monitor = task_monitor
        self.concurrency = concurrency
        self._queue: Optional[asyncio.Queue] = None
        self.is_running = False
        self.active_downloads = 0
        self.batch_total = 0
        self.completed_downloads = 0
        self.is_paused = False
        self._pending_downloads: set[tuple[str, str]] = set()
        self._worker_tasks: List[asyncio.Task] = []

    @property
    def queue(self) -> asyncio.PriorityQueue:
        if self._queue is None:
            self._queue = asyncio.PriorityQueue()
        return self._queue

    def enqueue_download(self, url: str, subfolder: str, filename: str, priority: int = 100) -> None:
        """Enqueue an image asset to be downloaded in the background."""
        if hasattr(self, "loop") and self.loop and self.loop.is_running():
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop == self.loop:
                self.loop.create_task(self._put_in_queue(url, subfolder, filename, priority))
            else:
                asyncio.run_coroutine_threadsafe(self._put_in_queue(url, subfolder, filename, priority), self.loop)
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(self._put_in_queue(url, subfolder, filename, priority))
            return

        # Background resolver threads do not have a durable event loop.
        # Fall back to an immediate download so adult assets still get cached.
        self.batch_total += 1
        try:
            self._do_download(url, subfolder, filename)
        finally:
            self.completed_downloads += 1

    async def _put_in_queue(self, url: str, subfolder: str, filename: str, priority: int = 100) -> None:
        if not self.is_running:
            await self.start()
        key = (subfolder, filename)
        if key in self._pending_downloads:
            return
        self._pending_downloads.add(key)
        if self.queue.empty() and self.active_downloads == 0:
            self.batch_total = 0
            self.completed_downloads = 0
        self.batch_total += 1
        await self.queue.put((priority, (url, subfolder, filename)))
        logger.debug(f"Enqueued asset download: {url} -> {subfolder}/{filename} (priority: {priority})")

    async def start(self) -> None:
        """Starts the background worker processing loops."""
        if self.is_running:
            return
        self.is_running = True
        self.loop = asyncio.get_running_loop()
        self._queue = asyncio.PriorityQueue()
        self.image_service.ensure_folders()
        
        # Start multiple concurrent workers consuming from the same queue
        self._worker_tasks = [
            asyncio.create_task(self._process_queue(i))
            for i in range(self.concurrency)
        ]
        logger.info(f"DownloadWorker started with {self.concurrency} concurrent workers on loop {self.loop}.")

    async def stop(self) -> None:
        """Stops the background worker and cancels all running worker tasks."""
        self.is_running = False
        for task in self._worker_tasks:
            task.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        logger.info("DownloadWorker background tasks stopped.")

    async def download_now(self, url: str, subfolder: str, filename: str) -> Optional[str]:
        """Performs a synchronous/immediate download and thumbnail generation."""
        return await asyncio.to_thread(self._do_download, url, subfolder, filename)

    def _do_download(self, url: str, subfolder: str, filename: str) -> Optional[str]:
        """Helper to download and generate thumbnail in a thread pool."""
        orig_path = self.image_service.get_original_path(subfolder, filename)
        thumb_path = self.image_service.get_thumbnail_path(subfolder, filename)

        # 1. Reuse existing files to avoid expensive redownloads
        svg_orig_path = orig_path.with_suffix(".svg")
        if self.image_service.exists(orig_path):
            is_svg = False
            try:
                with open(orig_path, "rb") as f:
                    header = f.read(4096).strip().lower()
                    if header.startswith(b"<svg") or header.startswith(b"<?xml") or b"<svg" in header:
                        is_svg = True
            except:
                pass

            if is_svg and not orig_path.name.lower().endswith(".svg"):
                if orig_path.exists():
                    if svg_orig_path.exists():
                        orig_path.unlink()
                    else:
                        orig_path.rename(svg_orig_path)
                return svg_orig_path.name

            logger.debug(f"Original asset already exists: {orig_path}. Re-generating thumbnail if missing.")
            if not self.image_service.exists(thumb_path):
                self.image_service.generate_thumbnail(orig_path, thumb_path, subfolder)
            return filename
        elif self.image_service.exists(svg_orig_path):
            logger.debug(f"Original SVG asset already exists: {svg_orig_path}.")
            return svg_orig_path.name

        # 2. Download original image
        logger.info(f"Downloading external asset: {url}")
        try:
            response = self.image_service.session.get(url, stream=True, timeout=HEAVY_IMAGE_DOWNLOAD_TIMEOUT)
            if response.status_code == 200:
                saved_path = self.image_service.write_chunks(orig_path, response.iter_content(chunk_size=8192), url=url)
                if saved_path:
                    import os
                    actual_filename = os.path.basename(saved_path)
                    orig_path = Path(saved_path)
                    thumb_path = self.image_service.get_thumbnail_path(subfolder, actual_filename)
                    # 3. Generate thumbnail
                    self.image_service.generate_thumbnail(orig_path, thumb_path, subfolder)
                    return actual_filename
                else:
                    logger.error(f"Failed to verify integrity of downloaded image: {url}")
            else:
                logger.error(f"Failed to download asset from {url}. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Exception downloading asset {url}: {e}")
        return None

    async def _process_queue(self, worker_id: int) -> None:
        """Main processing loop checking the async queue."""
        logger.debug(f"Download worker loop-{worker_id} started.")
        while self.is_running:
            try:
                # Pause/wait if any heavy tasks (scan, rename, undo) are running
                while self.is_paused or (self.task_monitor and self.task_monitor.has_active_heavy_tasks()):
                    await asyncio.sleep(2)

                priority, (url, subfolder, filename) = await self.queue.get()
                if self.is_paused or (self.task_monitor and self.task_monitor.has_active_heavy_tasks()):
                    await self.queue.put((priority, (url, subfolder, filename)))
                    self.queue.task_done()
                    await asyncio.sleep(0.25)
                    continue

                self.active_downloads += 1
                try:
                    await asyncio.to_thread(self._do_download, url, subfolder, filename)
                except Exception as e:
                    logger.error(f"Worker-{worker_id} error executing queued download for {url}: {e}")
                finally:
                    self.active_downloads = max(0, self.active_downloads - 1)
                    self.completed_downloads += 1
                    self._pending_downloads.discard((subfolder, filename))
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception in DownloadWorker loop-{worker_id}: {e}")
                await asyncio.sleep(2)

