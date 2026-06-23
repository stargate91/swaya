from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional

from app.shared_kernel.database import get_db
from app.domains.users.models import User, UserOverride, CustomList
from app.domains.users.schemas import (
    UserRead,
    UserCreate,
    UserOverrideRead,
    UserOverrideCreate,
    CustomListRead,
    CustomListCreate,
    ItemOverridesUpdate,
    ItemStatusUpdate,
    ImageOverrideUpdate,
    BulkOverridesUpdate,
    BulkTagsUpdate,
    BulkWatchedUpdate,
    TagResponse,
    CustomListResponse,
    CustomListDetailResponse,
    ListMembershipResponse,
    CustomListItemResponse,
    CatalogResponse,
    BulkUpdateResponse,
)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


# --- User Profiles ---

@router.get("", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    """Retrieve all users."""
    return db.query(User).all()


@router.post("", response_model=UserRead)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user profile."""
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    is_first_user = db.query(User.id).first() is None
    role = "owner" if is_first_user else (user_data.role or "member")
    if role not in {"owner", "member", "child"}:
        raise HTTPException(status_code=400, detail="Invalid user role")
    if role == "owner" and not is_first_user:
        raise HTTPException(status_code=400, detail="Owner profile already exists")
    if role == "child" and not user_data.managed_by_user_id:
        raise HTTPException(status_code=400, detail="Child profile requires a managing user")
    if user_data.managed_by_user_id:
        manager = db.get(User, user_data.managed_by_user_id)
        if not manager or manager.role not in {"owner", "member"}:
            raise HTTPException(status_code=400, detail="Invalid managing user")

    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=user_data.password_hash,
        pin_hash=user_data.pin_hash,
        role=role,
        managed_by_user_id=user_data.managed_by_user_id,
        allow_adult=user_data.allow_adult if role != "child" else False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- User Overrides ---

@router.get("/{user_id}/overrides", response_model=List[UserOverrideRead])
def list_user_overrides(user_id: int, db: Session = Depends(get_db)):
    """Retrieve all metadata and physical asset overrides for a user."""
    return db.query(UserOverride).filter(UserOverride.user_id == user_id).all()


@router.post("/{user_id}/overrides", response_model=UserOverrideRead)
def create_user_override(user_id: int, override_data: UserOverrideCreate, db: Session = Depends(get_db)):
    """Create or update a user override for a specific media item, performer, or collection."""
    # Find existing override for same resource to avoid duplicates
    query = db.query(UserOverride).filter(UserOverride.user_id == user_id)
    if override_data.media_item_id:
        query = query.filter(UserOverride.media_item_id == override_data.media_item_id)
    elif override_data.metadata_match_id:
        query = query.filter(UserOverride.metadata_match_id == override_data.metadata_match_id)
    elif override_data.person_id:
        query = query.filter(UserOverride.person_id == override_data.person_id)
    elif override_data.studio_id:
        query = query.filter(UserOverride.studio_id == override_data.studio_id)
    elif override_data.collection_id:
        query = query.filter(UserOverride.collection_id == override_data.collection_id)
    else:
        raise HTTPException(status_code=400, detail="Must target at least one resource ID")

    override = query.first()
    if not override:
        override = UserOverride(
            user_id=user_id,
            media_item_id=override_data.media_item_id,
            metadata_match_id=override_data.metadata_match_id,
            person_id=override_data.person_id,
            studio_id=override_data.studio_id,
            collection_id=override_data.collection_id,
        )
        db.add(override)

    # Apply values
    override.custom_title = override_data.custom_title
    override.custom_overview = override_data.custom_overview
    override.custom_poster = override_data.custom_poster
    override.custom_backdrop = override_data.custom_backdrop
    override.custom_logo = override_data.custom_logo
    override.custom_language = override_data.custom_language
    override.custom_edition = override_data.custom_edition
    override.custom_audio_type = override_data.custom_audio_type
    override.custom_source = override_data.custom_source
    override.user_rating = override_data.user_rating
    override.user_comment = override_data.user_comment
    override.is_favorite = override_data.is_favorite
    override.is_watched = override_data.is_watched
    override.is_tracked = override_data.is_tracked

    db.commit()
    db.refresh(override)
    return override


# --- Custom User Lists ---

@router.get("/{user_id}/lists", response_model=List[CustomListRead])
def list_user_custom_lists(user_id: int, db: Session = Depends(get_db)):
    """Retrieve custom user lists."""
    return db.query(CustomList).filter(CustomList.user_id == user_id).all()

# Compatibility API owned by the Users domain.
catalog_router = APIRouter(prefix="/api/v1", tags=["User Catalog"])

from app.domains.users.services.tags_service import TagsService
from app.application.catalog.lists_service import ListsService


@catalog_router.get("/tags", response_model=List[TagResponse])
def get_all_tags(target_type: Optional[str] = None, is_adult: bool = False, db: Session = Depends(get_db)):
    return TagsService(db).get_all_tags(target_type, is_adult)


@catalog_router.post("/tags", response_model=TagResponse)
def create_tag(payload: dict, db: Session = Depends(get_db)):
    return TagsService(db).create_tag(payload)


@catalog_router.put("/tags/{tag_id}", response_model=TagResponse)
def update_tag(tag_id: int, payload: dict, db: Session = Depends(get_db)):
    return TagsService(db).update_tag(tag_id, payload)


@catalog_router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    return TagsService(db).delete_tag(tag_id)


@catalog_router.get("/lists", response_model=List[CustomListResponse])
def get_all_lists(db: Session = Depends(get_db)):
    return ListsService(db).get_all_lists()


@catalog_router.get("/lists/item-membership/{item_id}", response_model=ListMembershipResponse)
def get_item_membership(item_id: str, db: Session = Depends(get_db)):
    return ListsService(db).get_item_membership(item_id)


@catalog_router.get("/lists/{list_id}", response_model=CustomListDetailResponse)
def get_list_details(list_id: int, db: Session = Depends(get_db)):
    return ListsService(db).get_list_details(list_id)


@catalog_router.post("/lists", response_model=CustomListResponse)
def create_list(payload: dict, db: Session = Depends(get_db)):
    return ListsService(db).create_list(payload)


@catalog_router.put("/lists/{list_id}", response_model=CustomListDetailResponse)
def update_list(list_id: int, payload: dict, db: Session = Depends(get_db)):
    return ListsService(db).update_list(list_id, payload)


@catalog_router.delete("/lists/{list_id}")
def delete_list(list_id: int, db: Session = Depends(get_db)):
    return ListsService(db).delete_list(list_id)


@catalog_router.post("/lists/{list_id}/items", response_model=CustomListItemResponse)
def add_item_to_list(list_id: int, payload: dict, db: Session = Depends(get_db)):
    return ListsService(db).add_item_to_list(list_id, payload)


@catalog_router.delete("/lists/{list_id}/items/{item_id}")
def remove_item_from_list(list_id: int, item_id: int, db: Session = Depends(get_db)):
    return ListsService(db).remove_item_from_list(list_id, item_id)



@catalog_router.get("/user/catalog", response_model=CatalogResponse)
def get_user_catalog(
    tab: Optional[str] = None,
    offset: int = 0,
    limit: int = 40,
    search: str = "",
    favorite_only: bool = False,
    db: Session = Depends(get_db),
):
    return ListsService(db).get_user_catalog(tab, offset, limit, search, favorite_only)


@catalog_router.post("/user/catalog/bulk-status", response_model=BulkUpdateResponse)
def bulk_update_catalog_status(payload: dict, db: Session = Depends(get_db)):
    return ListsService(db).bulk_update_catalog_status(payload)


from app.domains.users.services.overrides_service import OverridesService
from app.infrastructure.media.db_media_resolver import DbMediaResolver

@catalog_router.post("/media/update")
def update_item_overrides(payload: ItemOverridesUpdate, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).update_item_overrides(payload)

@catalog_router.post("/item/{item_id}/status")
def update_item_status(item_id: str, payload: ItemStatusUpdate, db: Session = Depends(get_db)):
    service = OverridesService(db, DbMediaResolver(db))
    res = {}
    if payload.status is not None:
        try:
            item_id_int = int(item_id)
            res.update(service.update_item_status(item_id_int, payload.status))
        except ValueError:
            pass
    has_overrides = any(
        getattr(payload, field) is not None
        for field in ["user_rating", "user_comment", "is_favorite", "is_watched", "custom_tags", "tags", "resume_position"]
    )
    if has_overrides:
        overrides_payload = ItemOverridesUpdate(
            item_id=item_id,
            user_rating=payload.user_rating,
            user_comment=payload.user_comment,
            is_favorite=payload.is_favorite,
            is_watched=payload.is_watched,
            tags=payload.custom_tags if payload.custom_tags is not None else payload.tags,
            resume_position=payload.resume_position,
        )
        res.update(service.update_item_overrides(overrides_payload))
    return res

@catalog_router.post("/item/{item_id}/poster")
def update_item_poster(item_id: str, payload: ImageOverrideUpdate, db: Session = Depends(get_db)):
    path = payload.path or payload.url or payload.poster_path
    if not path:
        raise HTTPException(status_code=400, detail="Image path/url is required")
    return OverridesService(db, DbMediaResolver(db)).update_item_image(item_id, "poster", path)

@catalog_router.post("/item/{item_id}/backdrop")
def update_item_backdrop(item_id: str, payload: ImageOverrideUpdate, db: Session = Depends(get_db)):
    path = payload.path or payload.url or payload.backdrop_path
    if not path:
        raise HTTPException(status_code=400, detail="Image path/url is required")
    return OverridesService(db, DbMediaResolver(db)).update_item_image(item_id, "backdrop", path)

@catalog_router.post("/item/{item_id}/logo")
def update_item_logo(item_id: str, payload: ImageOverrideUpdate, db: Session = Depends(get_db)):
    path = payload.path or payload.url or payload.logo_path
    if not path:
        raise HTTPException(status_code=400, detail="Image path/url is required")
    return OverridesService(db, DbMediaResolver(db)).update_item_image(item_id, "logo", path)

@catalog_router.post("/item/{item_id}/upload-poster")
def upload_item_poster(item_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).handle_image_upload(item_id, "poster", file.filename, file.file)

@catalog_router.post("/item/{item_id}/upload-backdrop")
def upload_item_backdrop(item_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).handle_image_upload(item_id, "backdrop", file.filename, file.file)

@catalog_router.post("/item/{item_id}/upload-logo")
def upload_item_logo(item_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).handle_image_upload(item_id, "logo", file.filename, file.file)

@catalog_router.post("/media/bulk-update")
def bulk_update(payload: BulkOverridesUpdate, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).bulk_update(payload)

@catalog_router.post("/media/bulk-tags")
def bulk_tags(payload: BulkTagsUpdate, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).bulk_tags(payload)

@catalog_router.post("/media/bulk-watched")
def bulk_watched(payload: BulkWatchedUpdate, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).bulk_watched(payload)

@catalog_router.post("/library/item/{item_id}/track")
def track_item(item_id: str, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).track_item(item_id, True)

@catalog_router.post("/library/item/{item_id}/untrack")
def untrack_item(item_id: str, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).track_item(item_id, False)