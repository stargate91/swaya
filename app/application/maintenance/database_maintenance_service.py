import logging
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.shared_kernel.database import Base
from app.domains.users.models import User

logger = logging.getLogger(__name__)


class DatabaseMaintenanceService:
    def __init__(self, db: Session):
        self.db = db

    def clear_database(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._load_main_metadata()
        options = options or {"all": True}
        try:
            self.db.execute(text("PRAGMA foreign_keys = OFF"))
            deleted_tables = []

            if options.get("all") or options.get("wipe"):
                excluded_tables = {"api_caches", "alembic_version", "system_settings", "user_settings", "users"}
                for table in reversed(Base.metadata.sorted_tables):
                    if table.name in excluded_tables:
                        continue
                    self.db.execute(table.delete())
                    deleted_tables.append(table.name)

                self._reset_sqlite_sequences(deleted_tables)
                self._ensure_default_user()

            self.db.execute(text("PRAGMA foreign_keys = ON"))
            self.db.commit()
            return {"status": "success", "deleted_tables": deleted_tables}
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database clear failed: {e}")
            return {"status": "error", "message": str(e)}

    def _ensure_default_user(self) -> None:
        exists = self.db.query(User).filter(User.id == 1).first()
        if not exists:
            self.db.add(User(
                id=1,
                username="default_user",
                email="default@swaya.io",
                password_hash="",
                allow_adult=True,
            ))

    def _load_main_metadata(self) -> None:
        import app.domains.tasks.models
        import app.domains.history.models
        import app.domains.library.models
        import app.domains.metadata.models
        import app.domains.people.models
        import app.domains.settings.models
        import app.domains.users.models

    def _reset_sqlite_sequences(self, table_names: list[str]) -> None:
        has_sequence_table = self.db.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
        ).first()
        if not has_sequence_table:
            return

        for table_name in table_names:
            self.db.execute(
                text("DELETE FROM sqlite_sequence WHERE name = :table_name"),
                {"table_name": table_name},
            )
