from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.shared_kernel.database import get_db
from app.infrastructure.scrapers.gateway import scraper_gateway
from app.domains.people.models import Person
from app.domains.people.schemas import PersonRead

# Mainstream (SFW) People Router
mainstream_router = APIRouter(prefix="/api/v1/mainstream/people", tags=["Mainstream People"])

# Adult (NSFW) People Router
adult_router = APIRouter(prefix="/api/v1/adult/people", tags=["Adult People"])

# General People Router
router = APIRouter(prefix="/api/v1/people", tags=["General People"])


# --- Mainstream Router Endpoints ---
@mainstream_router.get("", response_model=List[PersonRead])
def list_mainstream_people(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve mainstream cast/crew (SFW)."""
    return db.query(Person).filter(Person.is_adult == False).limit(limit).all()


# --- Adult Router Endpoints ---
@adult_router.get("", response_model=List[PersonRead])
def list_adult_people(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve adult performers (NSFW)."""
    return db.query(Person).filter(Person.is_adult == True).limit(limit).all()


# --- General Router Endpoints ---


async def run_people_enrich_coroutine(task_id: int, match_ids: List[int]):
    import logging
    from app.shared_kernel.database import SessionLocal
    from app.domains.people.services.people_enricher import PeopleEnricher

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        enricher = PeopleEnricher(db, scraper_gateway)
        count = await asyncio.to_thread(enricher.enrich_people_for_matches, task_id, match_ids)
        logger.info(f"Enriched {count} people for matches {match_ids}")
    except Exception as e:
        logger.error(f"People enrichment task failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


@router.post("/enrich")
def enrich_people(match_ids: List[int], db: Session = Depends(get_db)):
    """
    Triggers a background task to enrich people details (bio, physical traits, profiles)
    for the given MetadataMatch IDs.
    """
    from app.domains.tasks import task_manager
    task_manager.people_enrich_worker.enqueue_enrich(match_ids)
    task_id = task_manager.people_enrich_worker.active_task_id
    return {"status": "enrichment_pending", "task_id": task_id}


# --- Detailed People Endpoints ---
from app.domains.people.services.people_detail_service import PeopleDetailService
from fastapi import Query

@router.get("")
def get_people(
    search: str = None,
    role: str = None,
    sort_by: str = "library_count",
    include_inactive: bool = False,
    adult_only: bool = False,
    gender: str = "all",
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_people(
        search=search, role=role, sort_by=sort_by, include_inactive=include_inactive,
        adult_only=adult_only, gender=gender, offset=offset, limit=limit
    )


@router.get("/{person_id}")
def get_person_detail(person_id: int, db: Session = Depends(get_db)):
    return PeopleDetailService(db, scraper_gateway).get_person_detail(person_id)


@router.get("/{person_id}/movies")
def get_person_movies(
    person_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_movies(person_id, page=page, page_size=page_size)


@router.get("/{person_id}/tv")
def get_person_tv(
    person_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_tv(person_id, page=page, page_size=page_size)


@router.get("/{person_id}/scenes")
def get_person_scenes(
    person_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_scenes(person_id, page=page, page_size=page_size)

