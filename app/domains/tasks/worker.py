import asyncio
import logging
from typing import Optional, List

from app.domains.media_assets.services.images import ImageProcessingService
from app.shared_kernel.constants import HEAVY_IMAGE_DOWNLOAD_TIMEOUT

logger = logging.getLogger(__name__)

class DownloadWorker:
    """
    Background worker that monitors and handles downloading of external media assets
    (posters, backdrops, logos, stills, performer profile images).
    Utilizes ImageProcessingService to store files and generate correct thumbnails.
    Supports concurrent processing of downloads.
    """

    def __init__(self, image_service: Optional[ImageProcessingService] = None, concurrency: int = 6):
        self.image_service = image_service or ImageProcessingService()
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
    def queue(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    def enqueue_download(self, url: str, subfolder: str, filename: str) -> None:
        """Enqueue an image asset to be downloaded in the background."""
        if hasattr(self, "loop") and self.loop and self.loop.is_running():
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop == self.loop:
                self.loop.create_task(self._put_in_queue(url, subfolder, filename))
            else:
                asyncio.run_coroutine_threadsafe(self._put_in_queue(url, subfolder, filename), self.loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._put_in_queue(url, subfolder, filename))
            except RuntimeError:
                asyncio.run(self._put_in_queue(url, subfolder, filename))

    async def _put_in_queue(self, url: str, subfolder: str, filename: str) -> None:
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
        await self.queue.put((url, subfolder, filename))
        logger.debug(f"Enqueued asset download: {url} -> {subfolder}/{filename}")

    async def start(self) -> None:
        """Starts the background worker processing loops."""
        if self.is_running:
            return
        self.is_running = True
        self.loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
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

    async def download_now(self, url: str, subfolder: str, filename: str) -> bool:
        """Performs a synchronous/immediate download and thumbnail generation."""
        return await asyncio.to_thread(self._do_download, url, subfolder, filename)

    def _do_download(self, url: str, subfolder: str, filename: str) -> bool:
        """Helper to download and generate thumbnail in a thread pool."""
        orig_path = self.image_service.get_original_path(subfolder, filename)
        thumb_path = self.image_service.get_thumbnail_path(subfolder, filename)

        # 1. Reuse existing files to avoid expensive redownloads
        if self.image_service.exists(orig_path):
            logger.debug(f"Original asset already exists: {orig_path}. Re-generating thumbnail if missing.")
            if not self.image_service.exists(thumb_path):
                self.image_service.generate_thumbnail(orig_path, thumb_path, subfolder)
            return True

        # 2. Download original image
        logger.info(f"Downloading external asset: {url}")
        try:
            response = self.image_service.session.get(url, stream=True, timeout=HEAVY_IMAGE_DOWNLOAD_TIMEOUT)
            if response.status_code == 200:
                saved_path = self.image_service.write_chunks(orig_path, response.iter_content(chunk_size=8192))
                if saved_path:
                    # 3. Generate thumbnail
                    self.image_service.generate_thumbnail(orig_path, thumb_path, subfolder)
                    return True
                else:
                    logger.error(f"Failed to verify integrity of downloaded image: {url}")
            else:
                logger.error(f"Failed to download asset from {url}. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Exception downloading asset {url}: {e}")
        return False

    async def _process_queue(self, worker_id: int) -> None:
        """Main processing loop checking the async queue."""
        logger.debug(f"Download worker loop-{worker_id} started.")
        while self.is_running:
            try:
                # Pause/wait if any heavy tasks (scan, rename, undo) are running
                from app.domains.tasks import task_manager
                while self.is_paused or task_manager.has_active_heavy_tasks():
                    await asyncio.sleep(2)

                url, subfolder, filename = await self.queue.get()
                if self.is_paused or task_manager.has_active_heavy_tasks():
                    await self.queue.put((url, subfolder, filename))
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
