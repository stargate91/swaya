from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.shared_kernel.database import get_db
from app.domains.history.models import PlaybackLog, PlaybackPeakLog, ActionBatch
from app.domains.history.schemas import (
    PlaybackLogRead,
    PlaybackPeakLogRead,
    ActionBatchRead,
)

router = APIRouter(prefix="/api/v1/history", tags=["History"])


# --- Playback History (Watched) ---

@router.get("/playback", response_model=List[PlaybackLogRead])
def get_playback_history(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve playback / watched history logs."""
    return db.query(PlaybackLog).order_by(PlaybackLog.watched_at.desc()).limit(limit).all()


# --- Peak Moments History ---

@router.get("/peaks", response_model=List[PlaybackPeakLogRead])
def get_peak_history(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve peak / hot-spot moments marked by users."""
    return db.query(PlaybackPeakLog).order_by(PlaybackPeakLog.created_at.desc()).limit(limit).all()


# --- Action Batches / File History ---

@router.get("/actions", response_model=List[ActionBatchRead])
def get_action_history(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve file/metadata auditing operation batches."""
    return db.query(ActionBatch).order_by(ActionBatch.created_at.desc()).limit(limit).all()


# --- Action Undo ---

async def run_undo_coroutine(task_id: int, batch_id: int):
    import logging
    from app.application.media.renamer_engine import RenamerEngine
    from app.shared_kernel.database import SessionLocal
    from app.domains.tasks import task_manager

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        engine = RenamerEngine(db)
        
        def progress_cb(current, total):
            progress = (current / total) * 100.0 if total > 0 else 100.0
            task_manager.update_progress(task_id, progress)
            
        def stop_check():
            return task_manager.is_cancelled(task_id)
            
        undone_count = engine.undo_batch(batch_id, progress_callback=progress_cb, stop_check=stop_check)
        logger.info(f"Undo complete for batch {batch_id}. Reverted {undone_count} items.")
    except Exception as e:
        logger.error(f"Undo coroutine failed for batch {batch_id}: {e}", exc_info=True)
        raise
    finally:
        db.close()

@router.post("/actions/{batch_id}/undo")
def undo_action_batch(batch_id: int, db: Session = Depends(get_db)):
    """
    Triggers a background task to undo a file/metadata operation batch.
    """
    batch = db.query(ActionBatch).filter(ActionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Action batch not found")
    
    from app.domains.tasks import task_manager
    task_id = task_manager.create_task(name=f"undo_batch_{batch_id}")
    task_manager.start_task(task_id, run_undo_coroutine, batch_id)
    
    return {"status": "undo_pending", "task_id": task_id, "batch_id": batch_id}
