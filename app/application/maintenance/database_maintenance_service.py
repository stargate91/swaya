import logging
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.tasks.models import BackgroundTask, ScraperLog
from app.domains.history.models import ActionBatch, ActionLog, PlaybackLog
from app.domains.media.models.filesystem import ExtraFile, Library, MediaItem
from app.domains.media.models.metadata import MetadataMatch
from app.domains.people.models import MediaPersonLink, Person, PersonLocalization
from app.domains.users.models import CustomList, CustomListItem

logger = logging.getLogger(__name__)


class DatabaseMaintenanceService:
    def __init__(self, db: Session):
        self.db = db

    def clear_database(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = options or {"all": True}
        try:
            self.db.execute(text("PRAGMA foreign_keys = OFF"))
            if options.get("all") or options.get("wipe"):
                self.db.query(ScraperLog).delete(synchronize_session=False)
                self.db.query(BackgroundTask).delete(synchronize_session=False)
                self.db.query(MediaPersonLink).delete(synchronize_session=False)
                self.db.query(PersonLocalization).delete(synchronize_session=False)
                self.db.query(Person).delete(synchronize_session=False)
                self.db.query(CustomListItem).delete(synchronize_session=False)
                self.db.query(CustomList).delete(synchronize_session=False)
                self.db.query(ActionLog).delete(synchronize_session=False)
                self.db.query(ActionBatch).delete(synchronize_session=False)
                self.db.query(PlaybackLog).delete(synchronize_session=False)
                self.db.query(ExtraFile).delete(synchronize_session=False)
                self.db.query(MetadataMatch).delete(synchronize_session=False)
                self.db.query(MediaItem).delete(synchronize_session=False)
                self.db.query(Library).delete(synchronize_session=False)

            self.db.execute(text("PRAGMA foreign_keys = ON"))
            self.db.commit()
            return {"status": "success"}
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database clear failed: {e}")
            return {"status": "error", "message": str(e)}
