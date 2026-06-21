import os
import sys
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.constants import DATABASE_TIMEOUT_SECONDS

class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base class shared by all domain models."""
    pass


def get_db_path(filename: str) -> str:
    """
    Resolves the database path.
    Defaults to the portable local 'data' directory in the application root.
    """
    local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    os.makedirs(local_dir, exist_ok=True)
    return os.path.join(local_dir, filename)


# Resolve database paths
SWAYA_DB_PATH = get_db_path("swaya.db")
CACHE_DB_PATH = get_db_path("cache.db")

# Create Engines with large pool size and overflow to avoid exhaustion under high concurrency
engine = create_engine(
    f"sqlite:///{SWAYA_DB_PATH}",
    pool_size=50,
    max_overflow=100,
    pool_timeout=60,
    connect_args={
        "timeout": DATABASE_TIMEOUT_SECONDS,
        "check_same_thread": False
    }
)

cache_engine = create_engine(
    f"sqlite:///{CACHE_DB_PATH}",
    pool_size=50,
    max_overflow=100,
    pool_timeout=60,
    connect_args={
        "timeout": DATABASE_TIMEOUT_SECONDS,
        "check_same_thread": False
    }
)


def configure_sqlite_engine(target_engine):
    """Applies high-performance SQLite WAL pragmas to the target engine."""
    @event.listens_for(target_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA cache_size=-64000;")  # 64MB Cache size
        cursor.close()


# Configure both engines with optimal SQLite PRAGMAs
configure_sqlite_engine(engine)
configure_sqlite_engine(cache_engine)

# Thread-safe session makers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
CacheSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cache_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_cache_db():
    db = CacheSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_databases():
    """
    Helper to initialize database tables.
    Main database tables are usually managed by Alembic, but this can serve
    as a fallback. Cache tables are created directly.
    """
    # Import all models here to ensure they register on Base.metadata
    import app.core.tasks.models
    import app.domains.history.models
    import app.domains.media.models
    import app.domains.people.models
    import app.domains.settings.models
    import app.domains.users.models
    
    # Create main database tables if they do not exist
    Base.metadata.create_all(bind=engine)
    
    # Ensure default user with id=1 exists to satisfy foreign key constraints
    from sqlalchemy.orm import Session
    from app.domains.users.models import User
    with Session(engine) as session:
        if not session.get(User, 1):
            default_user = User(
                id=1,
                username="default_user",
                email="default@swaya.io",
                password_hash="",
                allow_adult=True
            )
            session.add(default_user)
            session.commit()
    
    # Create cache tables in cache.db
    from app.domains.media.models.metadata import APICache
    APICache.__table__.create(bind=cache_engine, checkfirst=True)
    
    # Clean up orphaned child records in metadata tables due to legacy SQLite runs without foreign_keys=ON
    from sqlalchemy import text
    with Session(engine) as session:
        try:
            session.execute(text("DELETE FROM metadata_localizations WHERE match_id NOT IN (SELECT id FROM metadata_matches)"))
            session.execute(text("DELETE FROM media_person_links WHERE match_id NOT IN (SELECT id FROM metadata_matches)"))
            session.execute(text("DELETE FROM metadata_match_studios WHERE metadata_match_id NOT IN (SELECT id FROM metadata_matches)"))
            session.execute(text("DELETE FROM external_match_links WHERE match_id NOT IN (SELECT id FROM metadata_matches)"))
            session.execute(text("DELETE FROM user_overrides WHERE metadata_match_id IS NOT NULL AND metadata_match_id NOT IN (SELECT id FROM metadata_matches)"))
            session.execute(text("UPDATE background_tasks SET status = 'aborted', error_message = 'Server restarted' WHERE status IN ('running', 'pending')"))
            session.commit()
        except Exception as orphan_ex:
            logger.warning(f"Failed to clean up database orphans: {orphan_ex}")
            session.rollback()

