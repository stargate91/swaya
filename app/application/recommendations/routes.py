from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.shared_kernel.database import get_db
from app.application.recommendations.recommendations_service import RecommendationsService
from app.application.recommendations.schemas import (
    RecommendationsResponse,
    OrganizerGroupsResponse,
    ActionResponse,
)
from app.infrastructure.scrapers.support.gateway import scraper_gateway

router = APIRouter(prefix="/api/v1", tags=["Recommendations"])

class OrganizerDeleteRequest(BaseModel):
    item_ids: Optional[List[int]] = None
    extra_ids: Optional[List[int]] = None
    mode: str = "db_only"

class WatchlistRequest(BaseModel):
    tmdb_id: int
    type: str = "movie"

class OrganizerCountResponse(BaseModel):
    count: int

@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(language: Optional[str] = None, db: Session = Depends(get_db)):
    return RecommendationsService(db, scraper_gateway).get_recommendations(language=language)

@router.get("/organizer", response_model=OrganizerGroupsResponse)
def get_organizer_items(db: Session = Depends(get_db)):
    return RecommendationsService(db, scraper_gateway).get_organizer_groups()

@router.get("/organizer/count", response_model=OrganizerCountResponse)
def get_organizer_item_count(db: Session = Depends(get_db)):
    return {"count": RecommendationsService(db, scraper_gateway).get_organizer_item_count()}

@router.post("/organizer/delete", response_model=ActionResponse)
def delete_organizer_items(request: OrganizerDeleteRequest, db: Session = Depends(get_db)):
    return RecommendationsService(db, scraper_gateway).delete_organizer_items(
        item_ids=request.item_ids or [],
        extra_ids=request.extra_ids or [],
        mode=request.mode
    )

@router.post("/watchlist", response_model=ActionResponse)
def add_to_watchlist(request: WatchlistRequest, db: Session = Depends(get_db)):
    return RecommendationsService(db, scraper_gateway).add_to_watchlist(request.tmdb_id, request.type)

@router.delete("/watchlist/{tmdb_id}", response_model=ActionResponse)
def remove_from_watchlist(tmdb_id: int, db: Session = Depends(get_db)):
    return RecommendationsService(db, scraper_gateway).remove_from_watchlist(tmdb_id)
