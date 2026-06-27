from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Any
import logging

logger = logging.getLogger(__name__)

from app.shared_kernel.database import get_db
from app.infrastructure.scrapers.support.gateway import scraper_gateway
from app.domains.people.models import Person
from app.domains.people.services.people_status_service import PeopleStatusService
from app.application.people.schemas import (
    PersonRead,
    PeopleSearchResponse,
    PersonDetailResponse,
    PersonFilmographyResponse,
    PersonStatusUpdate,
    PersonAddTmdb,
    PersonLinkPayload,
    PersonUnlinkPayload,
)
from app.application.users.schemas import ImageOverrideUpdate

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
    return PeopleStatusService(db).list_people_by_type(is_adult=False, limit=limit)


# --- Adult Router Endpoints ---
@adult_router.get("", response_model=List[PersonRead])
def list_adult_people(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve adult performers (NSFW)."""
    return PeopleStatusService(db).list_people_by_type(is_adult=True, limit=limit)


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
def get_person_detail(person_id: str, db: Session = Depends(get_db)):
    return PeopleDetailService(db, scraper_gateway).get_person_detail(person_id)


@router.get("/{person_id}/movies", response_model=PersonFilmographyResponse)
def get_person_movies(
    person_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    source: str = Query(default=None),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_movies(person_id, page=page, page_size=page_size, source=source)


@router.get("/{person_id}/tv", response_model=PersonFilmographyResponse)
def get_person_tv(
    person_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_tv(person_id, page=page, page_size=page_size)


@router.get("/{person_id}/scenes", response_model=PersonFilmographyResponse)
def get_person_scenes(
    person_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1),
    source: str = Query(default=None),
    db: Session = Depends(get_db)
):
    return PeopleDetailService(db, scraper_gateway).get_person_scenes(person_id, page=page, page_size=page_size, source=source)


def resolve_person(person_id: Any, db: Session):
    return PeopleStatusService(db).resolve_person(person_id)


@router.post("/{person_id}/status")
def update_person_status(
    person_id: str,
    payload: PersonStatusUpdate,
    db: Session = Depends(get_db)
):
    return PeopleStatusService(db).update_person_status(
        person_id=person_id,
        payload_data=payload.model_dump(),
        fields_set=payload.model_fields_set,
    )


@router.get("/{person_id}/credit-backdrops")
def get_person_credit_backdrops(
    person_id: str,
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


@router.get("/{person_id}/link/preview")
def link_person_source_preview(
    person_id: str,
    source: str = Query(...),
    external_id: str = Query(...),
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    from app.domains.users.models import UserOverride
    from app.shared_kernel.user_context import get_current_user_id
    try:
        current_uid = get_current_user_id()
    except Exception:
        current_uid = None

    override_rec = None
    if current_uid:
        override_rec = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            UserOverride.person_id == person.id
        ).first()

    biography = None
    if person.localizations:
        loc = next((l for l in person.localizations if l.locale == "en"), person.localizations[0])
        biography = loc.biography

    local_data = {
        "name": person.name,
        "gender": person.gender,
        "birthday": person.birthday,
        "place_of_birth": person.place_of_birth,
        "height": person.height,
        "measurements": person.measurements,
        "ethnicity": person.ethnicity,
        "eye_color": person.eye_color,
        "hair_color": person.hair_color,
        "biography": biography,
        "user_rating": override_rec.user_rating if override_rec else None,
        "user_comment": override_rec.user_comment if override_rec else None,
        "is_favorite": override_rec.is_favorite if override_rec else False,
        "custom_tags": override_rec.custom_tags if override_rec else [],
    }

    external_data = {
        "name": None,
        "gender": 0,
        "birthday": None,
        "place_of_birth": None,
        "height": None,
        "measurements": None,
        "ethnicity": None,
        "eye_color": None,
        "hair_color": None,
        "biography": None,
        "aliases": [],
        "images_count": 0,
    }

    source_lower = source.lower()
    if source_lower == "tmdb":
        tmdb_details = None
        try:
            tmdb_client = scraper_gateway.tmdb(db)
            tmdb_details = tmdb_client.get_person_details(int(external_id))
        except Exception as e:
            logger.error(f"Error fetching tmdb details: {e}")

        if tmdb_details:
            external_data["name"] = tmdb_details.get("name")
            external_data["gender"] = tmdb_details.get("gender") or 0
            external_data["birthday"] = tmdb_details.get("birthday")
            external_data["place_of_birth"] = tmdb_details.get("place_of_birth")
            external_data["biography"] = tmdb_details.get("biography")
            external_data["aliases"] = tmdb_details.get("also_known_as") or []
            images = tmdb_details.get("images", {})
            profiles = images.get("profiles", []) if isinstance(images, dict) else []
            external_data["images_count"] = len(profiles)
    else:
        perf = None
        try:
            from app.shared_kernel.enums import Provider
            scraper_name = "porndb" if source_lower == "theporndb" else source_lower
            provider_enum = Provider(scraper_name)
            scraper_client = scraper_gateway.adult(provider_enum, db)
            perf = scraper_client.get_performer_details(external_id)
        except Exception as e:
            logger.error(f"Error fetching adult performer details: {e}")

        if perf:
            external_data["name"] = perf.get("name")
            g = perf.get("gender")
            if g:
                g_lower = str(g).lower()
                if "female" in g_lower:
                    external_data["gender"] = 1
                elif "male" in g_lower:
                    external_data["gender"] = 2
                else:
                    external_data["gender"] = 0
            external_data["birthday"] = perf.get("birth_date")
            external_data["ethnicity"] = perf.get("ethnicity")
            external_data["eye_color"] = perf.get("eye_color")
            external_data["hair_color"] = perf.get("hair_color")
            h = perf.get("height")
            if h is not None:
                try:
                    external_data["height"] = int(h)
                except (ValueError, TypeError):
                    pass
            m = perf.get("measurements")
            if m and isinstance(m, dict):
                band = m.get("band_size")
                cup = m.get("cup_size")
                waist = m.get("waist")
                hip = m.get("hip")
                if band and cup and waist and hip:
                    external_data["measurements"] = f"{band}{cup}-{waist}-{hip}"
            external_data["biography"] = perf.get("details")
            external_data["aliases"] = perf.get("aliases") or []
            external_data["images_count"] = len(perf.get("images") or [])

    return {"local": local_data, "external": external_data}


@router.post("/{person_id}/link")
def link_person_source(
    person_id: str,
    payload: PersonLinkPayload,
    db: Session = Depends(get_db)
):
    from fastapi.responses import JSONResponse
    from app.domains.people.models import Person, ExternalSourceLink, MediaPersonLink
    from app.domains.users.models import UserOverride
    from app.shared_kernel.enums import Provider
    import datetime

    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    source = payload.source.lower()
    external_id = payload.external_id
    overrides = payload.overrides

    try:
        provider_enum = Provider(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

    existing_link = db.query(ExternalSourceLink).filter(
        ExternalSourceLink.provider == provider_enum,
        ExternalSourceLink.external_id == external_id
    ).first()

    duplicate_person = None
    if existing_link:
        duplicate_person = existing_link.person

    if not duplicate_person and source == "tmdb":
        try:
            tmdb_int = int(external_id)
            duplicate_person = db.query(Person).filter(Person.id == tmdb_int).first()
        except ValueError:
            pass

    ext_ids = dict(person.external_ids or {})
    ext_ids[source] = str(external_id)
    ext_ids[f"{source}_id"] = str(external_id)
    if "source" not in ext_ids:
        ext_ids["source"] = source
    person.external_ids = ext_ids

    if source in ("stashdb", "fansdb", "theporndb", "porndb"):
        person.is_adult = True

    link = db.query(ExternalSourceLink).filter(
        ExternalSourceLink.person_id == person.id,
        ExternalSourceLink.provider == provider_enum,
        ExternalSourceLink.external_id == external_id
    ).first()
    if not link:
        link = ExternalSourceLink(
            person_id=person.id,
            provider=provider_enum,
            external_id=external_id,
            profile_url=payload.profile_url
        )
        db.add(link)
    else:
        if payload.profile_url:
            link.profile_url = payload.profile_url

    if overrides:
        from app.shared_kernel.user_context import get_current_user_id
        current_uid = get_current_user_id()
        
        override_rec = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            UserOverride.person_id == person.id
        ).first()
        if not override_rec:
            override_rec = UserOverride(
                user_id=current_uid,
                person_id=person.id
            )
            db.add(override_rec)
        
        if "is_favorite" in overrides:
            override_rec.is_favorite = bool(overrides["is_favorite"])
        if "user_rating" in overrides:
            override_rec.user_rating = overrides["user_rating"]
            override_rec.user_rating_at = datetime.datetime.utcnow()
        if "user_comment" in overrides:
            override_rec.user_comment = overrides["user_comment"]
        if "custom_tags" in overrides:
            override_rec.custom_tags = overrides["custom_tags"]

    if duplicate_person and duplicate_person.id != person.id:
        existing_links = db.query(MediaPersonLink).filter(MediaPersonLink.person_id == person.id).all()
        existing_match_roles = {(l.match_id, l.role) for l in existing_links}

        dup_links = db.query(MediaPersonLink).filter(MediaPersonLink.person_id == duplicate_person.id).all()
        for dl in dup_links:
            if (dl.match_id, dl.role) not in existing_match_roles:
                dl.person_id = person.id
            else:
                db.delete(dl)

        for ext_link in duplicate_person.external_links:
            exists = db.query(ExternalSourceLink).filter(
                ExternalSourceLink.person_id == person.id,
                ExternalSourceLink.provider == ext_link.provider,
                ExternalSourceLink.external_id == ext_link.external_id
            ).first()
            if not exists:
                ext_link.person_id = person.id
                target_ids = dict(person.external_ids or {})
                target_ids[ext_link.provider.value] = ext_link.external_id
                target_ids[f"{ext_link.provider.value}_id"] = ext_link.external_id
                person.external_ids = target_ids
            else:
                db.delete(ext_link)

        dup_overrides = db.query(UserOverride).filter(
            UserOverride.person_id == duplicate_person.id
        ).all()
        for do in dup_overrides:
            exists = db.query(UserOverride).filter(
                UserOverride.user_id == do.user_id,
                UserOverride.person_id == person.id
            ).first()
            if not exists:
                do.person_id = person.id
            else:
                if not exists.is_favorite and do.is_favorite:
                    exists.is_favorite = True
                if exists.user_rating is None and do.user_rating is not None:
                    exists.user_rating = do.user_rating
                    exists.user_rating_at = do.user_rating_at
                db.delete(do)

        db.delete(duplicate_person)

    # Dynamic enrichment after linking using TMDB > StashDB > FansDB > PornDB priority
    try:
        from app.domains.people.services.people_enricher import PeopleEnricher
        from app.shared_kernel.enums import Provider
        enricher = PeopleEnricher(db, scrapers=scraper_gateway)
        
        links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person.id).all()
        link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
        
        for prov_name, ext_id in (person.external_ids or {}).items():
            try:
                prov = Provider(prov_name.lower())
                if not any(ld["provider"] == prov for ld in link_data):
                    link_data.append({"provider": prov, "external_id": str(ext_id)})
            except Exception:
                pass

        fetched_data = enricher.fetch_external_details(
            person.name,
            person.external_ids or {},
            link_data,
            is_adult=person.is_adult
        )
        if fetched_data:
            enricher.apply_enriched_data(person, fetched_data)
    except Exception as e:
        logger.error(f"Failed to dynamically enrich linked person {person.id}: {e}", exc_info=True)

    db.commit()
    return {"status": "success", "linked_person_id": person.id}


@router.post("/{person_id}/unlink")
def unlink_person_source(
    person_id: str,
    payload: PersonUnlinkPayload,
    db: Session = Depends(get_db)
):
    from app.domains.people.models import Person, ExternalSourceLink, MediaPersonLink
    from app.shared_kernel.enums import Provider

    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    source = payload.source.lower()
    action = payload.action.lower()

    try:
        provider_enum = Provider(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

    link = db.query(ExternalSourceLink).filter(
        ExternalSourceLink.person_id == person.id,
        ExternalSourceLink.provider == provider_enum
    ).first()

    ext_ids = dict(person.external_ids or {})
    ext_ids.pop(source, None)
    ext_ids.pop(f"{source}_id", None)
    if ext_ids.get("source") == source:
        ext_ids.pop("source", None)
        for k in ["tmdb", "stashdb", "fansdb", "porndb", "theporndb"]:
            if k in ext_ids:
                ext_ids["source"] = k
                break
    person.external_ids = ext_ids

    if link:
        if link in person.external_links:
            person.external_links.remove(link)
        db.delete(link)
        db.flush()

    person.recalculate_projection(db)

    if action == "split":
        new_person = Person(
            name=f"{person.name} ({source.upper()})" if person.name else f"Split performer ({source})",
            is_adult=person.is_adult,
            known_for_department=person.known_for_department or "Acting",
            is_active=True,
            profile_path=link.profile_url if (link and link.profile_url) else person.profile_path,
            external_ids={
                source: link.external_id if link else "",
                f"{source}_id": link.external_id if link else "",
                "source": source
            }
        )
        db.add(new_person)
        db.flush()

        if link:
            new_link = ExternalSourceLink(
                person_id=new_person.id,
                provider=provider_enum,
                external_id=link.external_id,
                profile_url=link.profile_url,
                source_data=link.source_data
            )
            db.add(new_link)
            new_person.external_links.append(new_link)
            db.flush()
            new_person.recalculate_projection(db)

            # Dynamic enrichment for the new split performer
            try:
                from app.domains.people.services.people_enricher import PeopleEnricher
                enricher = PeopleEnricher(db, scrapers=scraper_gateway)
                
                link_data = [{"provider": provider_enum, "external_id": link.external_id}]
                fetched_data = enricher.fetch_external_details(
                    new_person.name,
                    new_person.external_ids or {},
                    link_data,
                    is_adult=new_person.is_adult
                )
                if fetched_data:
                    enricher.apply_enriched_data(new_person, fetched_data)
            except Exception as e:
                logger.error(f"Failed to enrich split person {new_person.id}: {e}", exc_info=True)

        from app.domains.metadata.models import MetadataMatch
        match_ids = db.query(MetadataMatch.id).filter(MetadataMatch.provider == provider_enum).all()
        match_ids_set = {mid for (mid,) in match_ids}

        person_links = db.query(MediaPersonLink).filter(
            MediaPersonLink.person_id == person.id
        ).all()

        for pl in person_links:
            if pl.match_id in match_ids_set:
                pl.person_id = new_person.id

    db.commit()
    return {"status": "success", "person_id": person.id}


from pydantic import BaseModel

class PersonPrimaryPayload(BaseModel):
    source: str

@router.post("/{person_id}/primary")
def set_primary_person_source(
    person_id: str,
    payload: PersonPrimaryPayload,
    db: Session = Depends(get_db)
):
    from app.shared_kernel.enums import Provider
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    source = payload.source.lower()
    if source == "none" or not source:
        person.primary_provider = None
    else:
        try:
            prov_enum = Provider(source)
            person.primary_provider = prov_enum
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

    person.recalculate_projection(db)
    db.commit()
    return {"status": "success", "person_id": person.id, "primary_provider": source}


class PersonFieldRoutingPayload(BaseModel):
    routing: dict[str, str]

@router.post("/{person_id}/field-routing")
def set_person_field_routing(
    person_id: str,
    payload: PersonFieldRoutingPayload,
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    person.field_routing = payload.routing
    person.recalculate_projection(db)
    db.commit()
    return {"status": "success", "person_id": person.id, "field_routing": person.field_routing}


class SaveCustomFieldsPayload(BaseModel):
    fields: dict[str, Any]

@router.post("/{person_id}/custom-fields")
def save_custom_fields(
    person_id: str,
    payload: SaveCustomFieldsPayload,
    db: Session = Depends(get_db)
):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    from app.domains.people.models import ExternalSourceLink
    from app.shared_kernel.enums import Provider

    manual_link = next((l for l in person.external_links if l.provider == Provider.MANUAL), None)
    if not manual_link:
        manual_link = ExternalSourceLink(
            person_id=person.id,
            provider=Provider.MANUAL,
            external_id=f"manual_{person.id}",
            source_data={}
        )
        db.add(manual_link)
        person.external_links.append(manual_link)

    source_data = dict(manual_link.source_data or {})
    for k, v in payload.fields.items():
        if v == "" or v is None or v == {}:
            source_data.pop(k, None)
            if k == "biography" or k == "biographies":
                source_data.pop("biography", None)
                source_data.pop("biographies", None)
        else:
            if k == "biographies":
                source_data["biographies"] = v
                source_data["biography"] = v.get("en") or next(iter(v.values()), None)
            elif k == "biography":
                if isinstance(v, dict):
                    source_data["biographies"] = v
                    source_data["biography"] = v.get("en") or next(iter(v.values()), None)
                else:
                    source_data["biography"] = v
                    if "biographies" not in source_data:
                        source_data["biographies"] = {"en": v, "hu": v}
            else:
                source_data[k] = v

    manual_link.source_data = source_data
    person.recalculate_projection(db)
    db.commit()

    return {"status": "success", "source_data": manual_link.source_data}


@router.delete("/{person_id}")
def delete_person(person_id: str, db: Session = Depends(get_db)):
    person = resolve_person(person_id, db)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    db.delete(person)
    db.commit()
    return {"status": "success"}

