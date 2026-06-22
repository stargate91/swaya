from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.shared_kernel.database import get_db
from app.shared_kernel.enums import ScanMode
from app.application.media.scanner_service import ScannerService

router = APIRouter(prefix="/api/v1", tags=["Media Operations"])

class ScanRequest(BaseModel):
    paths: List[str]
    stop_after: Optional[str] = None
    mode: ScanMode = ScanMode.MOVIES_TV
    include_adult: Optional[bool] = None

class RenameRequest(BaseModel):
    item_ids: Optional[List[int]] = None

@router.get("/scan-status")
def get_scan_status(db: Session = Depends(get_db)):
    return ScannerService(db).get_scan_status()

@router.get("/hydrate-status")
def get_hydrate_status(db: Session = Depends(get_db)):
    return ScannerService(db).get_hydrate_status()

@router.get("/image-status")
def get_image_status(db: Session = Depends(get_db)):
    return ScannerService(db).get_image_status()

@router.post("/reset-image-status")
def reset_image_status(db: Session = Depends(get_db)):
    return ScannerService(db).reset_image_status()

@router.post("/scan")
def start_scan(request: ScanRequest, db: Session = Depends(get_db)):
    return ScannerService(db).start_scan(
        request.paths,
        request.stop_after,
        request.mode,
        request.include_adult,
    )

@router.post("/task/stop")
def stop_active_task(db: Session = Depends(get_db)):
    return ScannerService(db).stop_active_task()

@router.post("/rename/start")
def start_rename(request: Optional[RenameRequest] = None, db: Session = Depends(get_db)):
    item_ids = request.item_ids if request else None
    return ScannerService(db).start_rename(item_ids)

@router.get("/history")
def get_history(page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    return ScannerService(db).get_history(page, limit)

@router.post("/rename/undo/{batch_id}")
def undo_rename(batch_id: int, db: Session = Depends(get_db)):
    return ScannerService(db).start_undo(batch_id)
