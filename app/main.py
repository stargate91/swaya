import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.shared_kernel.database import init_databases
from app.shared_kernel.logging import setup_logger
from app.domains.media_assets.services.images import ImageProcessingService

# Setup logging
setup_logger()
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize databases (e.g. creating cache tables if they don't exist)
    logger.info("Initializing databases...")
    init_databases()
    
    # Ensure image folders are created
    img_service = ImageProcessingService()
    img_service.ensure_folders()
    logger.info("Image directories ensured.")
    
    # Start background download worker on the main event loop
    from app.domains.tasks import task_manager
    from app.infrastructure.scrapers.gateway import scraper_gateway
    task_manager.people_enrich_worker.scrapers = scraper_gateway
    await task_manager.download_worker.start()
    await task_manager.people_enrich_worker.start()
    
    yield
    # Shutdown logic if any goes here
    await task_manager.download_worker.stop()
    await task_manager.people_enrich_worker.stop()
    logger.info("Application shutting down.")

app = FastAPI(
    title="Swaya Backend",
    version="1.0.0",
    lifespan=lifespan
)

from app.shared_kernel.exceptions import DomainException
from fastapi.responses import JSONResponse

@app.exception_handler(DomainException)
async def domain_exception_handler(request, exc: DomainException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message}
    )

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.domains.tasks.routes import router as tasks_router
from app.domains.library.routes import router as media_router, mainstream_router as media_mainstream_router, adult_router as media_adult_router, library_router
from app.domains.metadata.routes import library_router as metadata_router
from app.domains.people.routes import router as people_router, mainstream_router as people_mainstream_router, adult_router as people_adult_router
from app.domains.settings.routes import router as settings_router, db_router
from app.domains.users.routes import router as users_router, catalog_router
from app.domains.history.routes import router as history_router
from app.application.media.routes import router as app_media_router
from app.application.media.playback_routes import router as app_playback_router
from app.application.recommendations.routes import router as app_rec_router

app.include_router(tasks_router)
app.include_router(media_router)
app.include_router(media_mainstream_router)
app.include_router(media_adult_router)
app.include_router(library_router)
app.include_router(metadata_router)
app.include_router(people_router)
app.include_router(people_mainstream_router)
app.include_router(people_adult_router)
app.include_router(settings_router)
app.include_router(db_router)
app.include_router(users_router)
app.include_router(catalog_router)
app.include_router(history_router)
app.include_router(app_media_router)
app.include_router(app_playback_router)
app.include_router(app_rec_router)




# Resolve media directory path for static file serving
# This must match where ImageProcessingService saves images:
# e.g., <data_root>/media/images/original/... and <data_root>/media/images/thumbnails/...
media_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "media")))

# Ensure media folder exists
media_root.mkdir(parents=True, exist_ok=True)

logger.info(f"Mounting /media static files route pointing to: {media_root}")
app.mount("/media", StaticFiles(directory=str(media_root)), name="media")

@app.get("/")
def read_root():
    return {"status": "ok", "app": "Swaya Backend"}
