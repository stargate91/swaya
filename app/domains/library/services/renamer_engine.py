import logging
from typing import List, Optional, Any
from sqlalchemy.orm import Session

from app.domains.library.services.formatter.models import RenamePreview
from app.shared_kernel.ports.library_port import LibraryPort

# Import sub-services
from app.domains.library.services.path_template_compiler import PathTemplateCompiler
from app.domains.library.services.filesystem_renamer import FilesystemRenamer

logger = logging.getLogger(__name__)

class RenamerEngine:
    """
    Engine responsible for physical file operations (move, rename) and 
    maintaining consistency between the filesystem and the database.
    """

    def __init__(
        self,
        db_session: Session,
        library_port: Optional[LibraryPort] = None,
        formatter: Optional[Any] = None,
        move_with_progress_fn: Optional[Any] = None,
        send_to_trash_fn: Optional[Any] = None,
    ):
        self.db = db_session
        self.compiler = PathTemplateCompiler(library_port, formatter)
        self.renamer = FilesystemRenamer(
            db_session, library_port, self.compiler, move_with_progress_fn, send_to_trash_fn
        )

    def execute_batch(self, previews: List[RenamePreview], batch_name: Optional[str] = None) -> int:
        return self.renamer.execute_batch(previews, batch_name)

    def execute_single(self, preview: RenamePreview, batch_id: Optional[int] = None, progress_callback=None, organize_in_place: bool = False) -> bool:
        return self.renamer.execute_single(preview, batch_id, progress_callback, organize_in_place)

    def undo_batch(self, batch_id: int, progress_callback=None, stop_check=None) -> int:
        return self.renamer.undo_batch(batch_id, progress_callback, stop_check)
