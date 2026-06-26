from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.shared_kernel.database import get_db
from app.shared_kernel.enums import ScanMode
from app.domains.library.services.scanner_service import ScannerService

router = APIRouter(prefix="/api/v1", tags=["Media Operations"])

class ScanRequest(BaseModel):
    paths: List[str]
    stop_after: Optional[str] = None
    mode: ScanMode = ScanMode.MOVIES_TV
    include_adult: Optional[bool] = None
    provider: Optional[str] = None

class RenameRequest(BaseModel):
    item_ids: Optional[List[int]] = None

class RetryRequest(BaseModel):
    mode: ScanMode = ScanMode.MOVIES_TV
    include_adult: Optional[bool] = None
    provider: Optional[str] = None

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
    from app.infrastructure.scrapers.scan_resolver import ScanResolver
    return ScannerService(db, scan_resolver_factory=ScanResolver).start_scan(
        request.paths,
        request.stop_after,
        request.mode,
        request.include_adult,
        request.provider,
    )

@router.post("/scan/retry")
def start_retry(request: RetryRequest, db: Session = Depends(get_db)):
    from app.infrastructure.scrapers.scan_resolver import ScanResolver
    return ScannerService(db, scan_resolver_factory=ScanResolver).start_retry(
        request.mode,
        request.include_adult,
        request.provider,
    )

@router.post("/task/stop")
def stop_active_task(db: Session = Depends(get_db)):
    return ScannerService(db).stop_active_task()

@router.post("/rename/start")
def start_rename(request: Optional[RenameRequest] = None, db: Session = Depends(get_db)):
    item_ids = request.item_ids if request else None
    return ScannerService(db).start_rename(item_ids)

from app.application.history.schemas import HistoryResponse

@router.get("/history", response_model=HistoryResponse)
def get_history(page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    from app.domains.history.services.history_service import HistoryService
    return HistoryService(db).get_history(page, limit)

@router.post("/rename/undo/{batch_id}")
def undo_rename(batch_id: int, db: Session = Depends(get_db)):
    return ScannerService(db).start_undo(batch_id)


@router.get("/media/image-proxy")
def image_proxy(url: str = Query(..., description="The remote image URL to proxy")):
    import requests
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from urllib.parse import urlparse
    import logging
    import traceback
    import urllib3
    
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logger = logging.getLogger("app.media.image_proxy")
    
    if url.startswith("//"):
        url = "https:" + url
        
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
        response.raise_for_status()
        
        content_type = response.headers.get("Content-Type", "image/jpeg")
        return StreamingResponse(response.iter_content(chunk_size=4096), media_type=content_type)
    except Exception as e:
        logger.exception(f"Image proxy failed for URL {url}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch remote image: {e}")

