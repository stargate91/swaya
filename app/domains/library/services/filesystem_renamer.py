import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Any
from sqlalchemy.orm import Session

from app.shared_kernel.enums import ActionType, ActionStatus, ItemStatus
from app.domains.library.services.formatter.models import RenamePreview
from app.shared_kernel.ports.library_port import LibraryPort
from app.domains.library.services.path_template_compiler import PathTemplateCompiler

logger = logging.getLogger(__name__)

class FilesystemRenamer:
    def __init__(
        self,
        db_session: Session,
        library_port: LibraryPort,
        compiler: PathTemplateCompiler,
        move_with_progress_fn: Optional[Any] = None,
        send_to_trash_fn: Optional[Any] = None,
    ):
        self.db = db_session
        self.library_port = library_port
        self.compiler = compiler
        self.move_with_progress_fn = move_with_progress_fn
        self.send_to_trash_fn = send_to_trash_fn

    def execute_batch(self, previews: List[RenamePreview], batch_name: Optional[str] = None) -> int:
        batch_id = self.library_port.create_action_batch(batch_name or "Rename batch")

        success_count = 0
        for preview in previews:
            if self.execute_single(preview, batch_id):
                success_count += 1
        
        self.db.commit()
        return success_count

    def execute_single(self, preview: RenamePreview, batch_id: Optional[int] = None, progress_callback=None, organize_in_place: bool = False) -> bool:
        item = self.library_port.get_item_by_id(preview.item_id)
        if not item:
            return False
        batch_id = self._ensure_batch_id(batch_id)

        successful_moves = []

        try:
            preview_action = self.compiler._preview_action(preview)
            if preview_action == "skip":
                self._log_action(batch_id, item_id=item.id, action_type=ActionType.METADATA_UPDATE,
                                status=ActionStatus.SUCCESS, old_val=item.current_path,
                                new_val=item.current_path, error="Skipped due to collision strategy.")
                self.db.flush()
                return True

            old_path = Path(item.current_path)
            target_path = Path(preview.target_path)

            if not old_path.exists():
                raise FileNotFoundError(f"Source not found: {old_path}")

            if target_path.exists() and target_path != old_path:
                if target_path.is_dir():
                    raise FileExistsError(f"Directory exists at target: {target_path}")
                if preview_action == "replace_if_better":
                    if not self.compiler._is_better_replacement(item, target_path):
                        self._log_action(batch_id, item_id=item.id, action_type=ActionType.METADATA_UPDATE,
                                        status=ActionStatus.SUCCESS, old_val=item.current_path,
                                        new_val=str(target_path), error="Skipped because existing file is not worse.")
                        self.db.flush()
                        return True
                    self._remove_existing_target(target_path, batch_id, item)
                elif preview_action == "replace":
                    self._remove_existing_target(target_path, batch_id, item)
                else:
                    raise FileExistsError(f"File exists at target: {target_path}")

            for extra_preview in preview.extra_previews:
                extra = self.library_port.get_extra_by_id(extra_preview.extra_id)
                if not extra:
                    continue

                e_old = Path(extra.current_path)
                if not e_old.exists():
                    raise FileNotFoundError(f"Extra source not found: {e_old}")

                extra_action = self.compiler._preview_action(extra_preview)
                if extra_action == "skip":
                    continue

                if extra_action != "delete":
                    e_target = Path(extra_preview.target_path)
                    if e_target.exists() and e_target != e_old:
                        if e_target.is_dir():
                            raise FileExistsError(f"Directory exists at extra target: {e_target}")
                        raise FileExistsError(f"File exists at extra target: {e_target}")

            if target_path != old_path:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if self.move_with_progress_fn:
                    self.move_with_progress_fn(str(old_path), str(target_path), progress_callback)
                else:
                    shutil.move(str(old_path), str(target_path))
                successful_moves.append((old_path, target_path))
            
            for extra_preview in preview.extra_previews:
                extra = self.library_port.get_extra_by_id(extra_preview.extra_id)
                if not extra: continue

                e_old = Path(extra.current_path)
                if not e_old.exists():
                    raise FileNotFoundError(f"Extra source not found: {e_old}")

                extra_action = self.compiler._preview_action(extra_preview)
                if extra_action == "skip":
                    continue

                if extra_action == "delete":
                    if self.send_to_trash_fn:
                        self.send_to_trash_fn([e_old])
                    else:
                        os.remove(e_old)
                    successful_moves.append((e_old, None))
                else:
                    e_target = Path(extra_preview.target_path)
                    if e_target.exists() and e_target != e_old:
                        if e_target.is_dir():
                            raise FileExistsError(f"Directory exists at extra target: {e_target}")
                        raise FileExistsError(f"File exists at extra target: {e_target}")
                    e_target.parent.mkdir(parents=True, exist_ok=True)
                    if e_target != e_old:
                        shutil.move(str(e_old), str(e_target))
                        successful_moves.append((e_old, e_target))

            old_item_path = item.current_path
            status_to_set = ItemStatus.ORGANIZED if organize_in_place else ItemStatus.RENAMED
            self.library_port.update_item_path_and_status(item.id, str(target_path), status_to_set)
            self._log_action(batch_id, item_id=item.id, action_type=ActionType.RENAME, 
                            status=ActionStatus.SUCCESS, old_val=old_item_path, new_val=str(target_path))

            for extra_preview in preview.extra_previews:
                extra = self.library_port.get_extra_by_id(extra_preview.extra_id)
                if extra:
                    old_e_path = extra.current_path
                    extra_action = self.compiler._preview_action(extra_preview)
                    if extra_action == "skip":
                        self._log_action(batch_id, extra_id=extra.id, action_type=ActionType.METADATA_UPDATE,
                                        status=ActionStatus.SUCCESS, old_val=old_e_path,
                                        new_val=old_e_path, error="Skipped due to collision strategy.")
                    elif extra_action == "delete":
                        self.library_port.delete_extra(extra.id)
                        self._log_action(batch_id, extra_id=None, action_type=ActionType.DELETE, 
                                        status=ActionStatus.SUCCESS, old_val=old_e_path, new_val=None)
                    else:
                        self.library_port.update_extra_path(extra.id, extra_preview.target_path)
                        self._log_action(batch_id, extra_id=extra.id, action_type=ActionType.RENAME, 
                                        status=ActionStatus.SUCCESS, old_val=old_e_path, new_val=extra_preview.target_path)

            self.db.flush()
            self._cleanup_empty_parent(old_path.parent)
            return True

        except Exception as e:
            logger.error(f"Error during rename ({preview.target_name}): {e}")
            self.db.rollback()

            if successful_moves:
                logger.info(f"Rolling back {len(successful_moves)} files...")
                for orig_p, curr_p in reversed(successful_moves):
                    try:
                        if curr_p is None:
                            logger.warning(f"Cannot rollback deleted file: {orig_p}")
                        elif curr_p.exists():
                            shutil.move(str(curr_p), str(orig_p))
                    except Exception as re:
                        logger.critical(f"CRITICAL: Rollback failed ({curr_p} -> {orig_p}): {re}")

            self._log_action(batch_id, item_id=item.id, action_type=ActionType.RENAME, 
                            status=ActionStatus.FAILED, old_val=item.current_path, 
                            new_val=preview.target_path, error=str(e))
            self.db.flush()
            return False

    def _ensure_batch_id(self, batch_id: Optional[int]) -> int:
        if batch_id is not None:
            return batch_id
        return self.library_port.create_action_batch("Single rename")

    def _remove_existing_target(self, target_path: Path, batch_id: int, source_item: Any):
        target_item = self.library_port.get_item_by_relative_path(str(target_path).replace("\\", "/"))
        if not target_item:
            target_item = self.library_port.get_item_by_absolute_path(str(target_path))

        if target_item:
            self.library_port.relink_relations_for_collision(target_item.id, source_item.id)
            self._log_action(batch_id, item_id=target_item.id, action_type=ActionType.DELETE,
                            status=ActionStatus.SUCCESS, old_val=target_item.current_path,
                            new_val=None, error="Replaced by collision strategy.")
            self.library_port.delete_item(target_item.id)
        
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete collision target file {target_path}: {e}")

    def _log_action(self, batch_id, item_id=None, extra_id=None, action_type=None, status=None, old_val=None, new_val=None, error=None):
        self.library_port.log_rename_action(
            batch_id=batch_id,
            item_id=item_id,
            extra_id=extra_id,
            action_type=action_type,
            status=status,
            old_val=old_val,
            new_val=new_val,
            error=error
        )

    def undo_batch(self, batch_id: int, progress_callback=None, stop_check=None) -> int:
        logs = self.library_port.get_action_logs_for_undo(batch_id)

        undo_count = 0
        total = len(logs)
        for i, log in enumerate(logs):
            if stop_check and stop_check():
                break
            if self._undo_single(log):
                undo_count += 1
            if progress_callback:
                progress_callback(i + 1, total)
        
        self.db.commit()
        return undo_count

    def _undo_single(self, log: Any) -> bool:
        try:
            if log.action_type not in [ActionType.RENAME, ActionType.MOVE]:
                return False

            new_path = Path(log.new_value)
            old_path = Path(log.old_value)

            if not new_path.exists():
                logger.error(f"Undo hiba: A fájl már nem található a célhelyen: {new_path}")
                self.library_port.update_action_log_status(log.id, ActionStatus.FAILED, "File missing at destination")
                return False

            old_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(new_path), str(old_path))

            if log.media_item_id:
                self.library_port.update_item_path_and_status(log.media_item_id, str(old_path), ItemStatus.MATCHED)
            elif log.extra_file_id:
                self.library_port.update_extra_path(log.extra_file_id, str(old_path))

            self.library_port.update_action_log_status(log.id, ActionStatus.UNDONE)
            self._cleanup_empty_parent(new_path.parent)
            return True

        except Exception as e:
            logger.exception(f"Undo hiba: {e}")
            self.db.rollback()
            return False

    def _cleanup_empty_parent(self, path: Path):
        try:
            if not path or path.parent == path:
                return

            if len(path.parts) <= 1:
                return

            protected_paths = set()
            try:
                libraries = self.library_port.get_all_libraries()
                for lib in libraries:
                    protected_paths.add(Path(lib.root_path).resolve())
            except Exception as e:
                logger.debug(f"Swallowed exception: {e}", exc_info=True)

            if path.resolve() in protected_paths:
                logger.debug(f"Cleanup stopped: {path} is a protected library root.")
                return

            if path.exists() and path.is_dir() and not any(path.iterdir()):
                logger.info(f"Cleaning up empty directory: {path}")
                path.rmdir()
                self._cleanup_empty_parent(path.parent)
        except Exception as e:
            logger.debug(f"Cleanup failed for {path}: {e}")
