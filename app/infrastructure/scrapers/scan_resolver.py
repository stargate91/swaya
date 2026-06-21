import time
import logging
import concurrent.futures
from typing import List, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.domains.library.models import MediaItem
from app.shared_kernel.enums import ItemStatus, ScanMode
from app.domains.settings.models import UserSetting, SystemSetting
from app.infrastructure.scrapers.resolver import Resolver
from app.infrastructure.scrapers.metadata_enricher import MetadataEnricher
from app.shared_kernel.database import SessionLocal
from app.shared_kernel.constants import DEFAULT_MAX_WORKERS, DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class ScanResolver:
    def __init__(
        self,
        db_session: Session,
        mode: ScanMode = ScanMode.MOVIES_TV,
        stop_checker: Optional[Callable[[], bool]] = None,
        include_adult: Optional[bool] = None,
    ):
        self.db = db_session
        self.mode = mode
        self.stop_checker = stop_checker
        self.include_adult = include_adult

    def _stop_requested(self, task_id: Optional[int] = None) -> bool:
        if self.stop_checker and self.stop_checker():
            return True
        if task_id is not None:
            from app.domains.tasks import task_manager
            if task_manager.is_cancelled(task_id):
                return True
        return False

    def resolve_all(self, items: List[MediaItem], progress_callback: Optional[Callable[[int, int], None]] = None, task_id: Optional[int] = None):
        if not items:
            return

        if self._stop_requested(task_id):
            logger.info("Scan stop requested before metadata resolution.")
            return

        logger.info(f"Phase 2: API Metadata Resolution for {len(items)} items...")

        # Deduplicate items by group_hash to avoid race conditions in propagate_match
        unique_items = []
        seen_hashes = set()
        for item in items:
            if not item.group_hash:
                unique_items.append(item)
            elif item.group_hash not in seen_hashes:
                unique_items.append(item)
                seen_hashes.add(item.group_hash)
        
        item_ids = [item.id for item in unique_items]
        total_items = len(item_ids)
        current_completed = 0

        # Read settings once on the scanner thread
        primary_lang = DEFAULT_FALLBACK_LANGUAGE
        fallback_lang = None
        try:
            pl = self.db.query(UserSetting).filter(UserSetting.key == "primary_metadata_language").first()
            if not pl:
                pl = self.db.query(SystemSetting).filter(SystemSetting.key == "primary_metadata_language").first()
            fl = self.db.query(UserSetting).filter(UserSetting.key == "fallback_metadata_language").first()
            if not fl:
                fl = self.db.query(SystemSetting).filter(SystemSetting.key == "fallback_metadata_language").first()
            
            if pl and pl.value:
                primary_lang = pl.value
            if fl and fl.value and fl.value != "none":
                fallback_lang = fl.value
        except Exception as settings_ex:
            logger.warning(f"Failed to load metadata language settings before resolution: {settings_ex}")

        def resolve_task(item_id: int):
            nonlocal current_completed
            max_attempts = 3
            try:
                for attempt in range(max_attempts):
                    if self._stop_requested(task_id):
                        return
                    local_db = SessionLocal()
                    try:
                        item = local_db.query(MediaItem).filter(MediaItem.id == item_id).first()
                        if not item:
                            return

                        if self._stop_requested(task_id):
                            return
                        resolver = Resolver(local_db)
                        resolver.resolve_item(
                            item,
                            mode=self.mode,
                            language=primary_lang,
                            task_id=task_id,
                            include_adult=self.include_adult,
                        )
                        
                        if self._stop_requested(task_id):
                            return
                        resolver.propagate_match(item)

                        if item.status == ItemStatus.MATCHED:
                            if self._stop_requested(task_id):
                                return
                            enricher = MetadataEnricher(local_db)
                            enricher.enrich_matched_item(item, language=primary_lang, fallback_language=fallback_lang)

                            if item.group_hash:
                                siblings = local_db.query(MediaItem).filter(
                                    MediaItem.group_hash == item.group_hash,
                                    MediaItem.id != item.id,
                                    MediaItem.status == ItemStatus.MATCHED
                                ).all()
                                for sib in siblings:
                                    try:
                                        if self._stop_requested(task_id):
                                            return
                                        enricher.enrich_matched_item(sib, language=primary_lang, fallback_language=fallback_lang)
                                    except Exception as sib_ex:
                                        logger.warning(f"Failed to enrich sibling item {sib.id}: {sib_ex}")
                        local_db.commit()
                        return
                    except OperationalError as e:
                        local_db.rollback()
                        if "database is locked" not in str(e).lower() or attempt == max_attempts - 1:
                            raise
                        wait_seconds = 0.25 * (attempt + 1)
                        logger.warning(f"Database was locked while resolving item ID {item_id}; retrying in {wait_seconds:.2f}s")
                        time.sleep(wait_seconds)
                    finally:
                        local_db.close()
            except Exception as e:
                import traceback
                logger.error(f"Error resolving item ID {item_id}: {e}")
                logger.error(traceback.format_exc())
                local_db = SessionLocal()
                try:
                    db_item = local_db.query(MediaItem).filter(MediaItem.id == item_id).first()
                    if db_item:
                        db_item.status = ItemStatus.ERROR
                        local_db.commit()
                except Exception as status_ex:
                    logger.error(f"Failed to set ERROR status for item ID {item_id}: {status_ex}")
                    local_db.rollback()
                finally:
                    local_db.close()
            finally:
                current_completed += 1
                if progress_callback:
                    try:
                        progress_callback(current_completed, total_items)
                    except Exception as cb_ex:
                        logger.warning(f"Progress callback raised exception: {cb_ex}")

        # ThreadPool for network requests (limited to avoid rate limit)
        from app.domains.tasks import task_manager
        executor = task_manager.executor
        max_workers = getattr(executor, "_max_workers", DEFAULT_MAX_WORKERS)
        
        future_to_item = {}
        item_iter = iter(item_ids)

        while not self._stop_requested(task_id):
            while len(future_to_item) < max_workers:
                try:
                    item_id = next(item_iter)
                except StopIteration:
                    break
                future = executor.submit(resolve_task, item_id)
                future_to_item[future] = item_id

            if not future_to_item:
                break

            done, _pending = concurrent.futures.wait(set(future_to_item.keys()), return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                future.result()
                future_to_item.pop(future, None)

        for future in list(future_to_item.keys()):
            future.result()

        logger.info("Resolution complete.")
