from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from sqlalchemy.orm import Session
from typing import List

from app.shared_kernel.database import get_db
from app.infrastructure.scrapers.support.gateway import scraper_gateway
from app.domains.people.models import Person
from app.domains.people.schemas import (
    PersonRead,
    PeopleSearchResponse,
    PersonDetailResponse,
    PersonFilmographyResponse,
    PersonStatusUpdate,
    PersonAddTmdb,
)
from app.domains.users.schemas import ImageOverrideUpdate

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

@router.get("", response_model=PeopleSearchResponse)
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


@router.post("/add-tmdb")
def add_person_tmdb(
    payload: PersonAddTmdb,
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).add_person_tmdb(
        db_id_or_external=payload.tmdb_id,
        name=payload.name,
        profile_path=payload.profile_path,
        gender=payload.gender,
        is_adult=payload.is_adult
    )



@router.get("/search-tmdb")
def search_people_tmdb(
    query: str,
    language: str = None,
    adult_only: bool = False,
    page: int = 1,
    source: str = "all",
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).search_people_tmdb(
        query=query, language=language, adult_only=adult_only, page=page, source=source
    )


@router.get("/{person_id}", response_model=PersonDetailResponse)
def get_person_detail(person_id: int, db: Session = Depends(get_db)):

    return PeopleDetailService(db, scraper_gateway).get_person_detail(person_id)


@router.get("/{person_id}/movies", response_model=PersonFilmographyResponse)
def get_person_movies(
    person_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    source: str = Query(default=None),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_movies(person_id, page=page, page_size=page_size, source=source)


@router.get("/{person_id}/tv", response_model=PersonFilmographyResponse)
def get_person_tv(
    person_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_tv(person_id, page=page, page_size=page_size)


@router.get("/{person_id}/scenes", response_model=PersonFilmographyResponse)
def get_person_scenes(
    person_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    source: str = Query(default=None),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_scenes(person_id, page=page, page_size=page_size, source=source)


def resolve_person(person_id: Any, db: Session):
    from app.domains.people.models import Person, ExternalSourceLink
    from app.shared_kernel.enums import Provider
    
    person_id_str = str(person_id)
    if ":" in person_id_str:
        parts = person_id_str.split(":", 1)
        source_name = parts[0]
        uuid_str = parts[1]
        
        scraper_name = "porndb" if source_name == "theporndb" else source_name
        try:
            provider_enum = Provider(scraper_name)
            link = db.query(ExternalSourceLink).filter(
                ExternalSourceLink.provider == provider_enum,
                ExternalSourceLink.external_id == uuid_str
            ).first()
            if link:
                return link.person
        except Exception:
            pass
        return None
    else:
        try:
            p_id = int(person_id_str)
            return db.query(Person).filter(Person.id == p_id).first()
        except (ValueError, TypeError):
            return None


@router.post("/{person_id}/status")
def update_person_status(
    person_id: str,
    payload: PersonStatusUpdate,
    db: Session = Depends(get_db)
):
    from datetime import datetime, timezone
    from app.domains.users.models import UserOverride
    from app.shared_kernel.user_context import get_current_user_id

    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    user_id = get_current_user_id() or 1
    fields_set = payload.model_fields_set

    # 1. Update Person level fields
    if "is_active" in fields_set and payload.is_active is not None:
        person.is_active = payload.is_active

    # Auto-activate on user interaction
    has_user_interaction = (
        ("user_rating" in fields_set and payload.user_rating is not None)
        or ("is_favorite" in fields_set and payload.is_favorite)
        or ("user_comment" in fields_set and payload.user_comment is not None)
    )
    if has_user_interaction:
        person.is_active = True

    # 2. Update UserOverride fields
    has_override_update = (
        "user_rating" in fields_set
        or "is_favorite" in fields_set
        or "user_comment" in fields_set
    )
    if has_override_update:
        override = db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person.id
        ).first()

        if not override:
            override = UserOverride(
                user_id=user_id,
                person_id=person.id
            )
            db.add(override)

        if "user_rating" in fields_set:
            override.user_rating = float(payload.user_rating) if payload.user_rating is not None else None
            override.user_rating_at = datetime.now(timezone.utc) if payload.user_rating is not None else None

        if "is_favorite" in fields_set:
            override.is_favorite = payload.is_favorite if payload.is_favorite is not None else False
            override.is_favorite_at = datetime.now(timezone.utc) if payload.is_favorite else None

        if "user_comment" in fields_set:
            override.user_comment = payload.user_comment
            override.user_comment_at = datetime.now(timezone.utc) if payload.user_comment else None

    db.commit()

    override = db.query(UserOverride).filter(
        UserOverride.user_id == user_id,
        UserOverride.person_id == person.id
    ).first()

    return {
        "status": "ok",
        "is_active": person.is_active,
        "is_favorite": override.is_favorite if override else False,
        "user_rating": override.user_rating if override else None,
        "user_comment": override.user_comment if override else None,
    }


@router.get("/{person_id}/credit-backdrops")
def get_person_credit_backdrops(
    person_id: int,
    tmdb_id: int = Query(..., ge=1),
    media_type: str = Query(...),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_credit_backdrops(
        person_id, tmdb_id=tmdb_id, media_type=media_type
    )


@router.post("/{person_id}/backdrop")
def update_person_backdrop(
    person_id: str,
    payload: ImageOverrideUpdate,
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    path = payload.path or payload.url or payload.backdrop_path
    if not path:
        raise HTTPException(status_code=400, detail="Backdrop path/url is required")
    return PeopleDetailService(db, scraper_gateway).update_person_backdrop(person.id, path)


@router.post("/{person_id}/upload-backdrop")
def upload_person_backdrop(
    person_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return PeopleDetailService(db, scraper_gateway).handle_person_backdrop_upload(
        person.id, file.filename, file.file
    )


@router.post("/{person_id}/profile")
def update_person_profile(
    person_id: str,
    payload: ImageOverrideUpdate,
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    path = payload.path or payload.url or payload.profile_path or payload.poster_path or payload.backdrop_path or payload.logo_path
    if not path:
        raise HTTPException(status_code=400, detail="Profile path/url is required")
    return PeopleDetailService(db, scraper_gateway).update_person_profile(person.id, path)


@router.post("/{person_id}/upload-profile")
def upload_person_profile(
    person_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return PeopleDetailService(db, scraper_gateway).handle_person_profile_upload(
        person.id, file.filename, file.file
    )

