from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.shared_kernel.database import get_db
from app.domains.users.models import User, UserOverride, CustomList
from app.domains.users.services.user_service import UserService
from app.application.users.schemas import (
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
    return UserService(db).list_users()


@router.post("", response_model=UserRead)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user profile."""
    return UserService(db).create_user(
        username=user_data.username,
        email=user_data.email,
        password_hash=user_data.password_hash,
        pin_hash=user_data.pin_hash,
        role=user_data.role,
        managed_by_user_id=user_data.managed_by_user_id,
        allow_adult=user_data.allow_adult,
    )


# --- User Overrides ---

@router.get("/{user_id}/overrides", response_model=List[UserOverrideRead])
def list_user_overrides(user_id: int, db: Session = Depends(get_db)):
    """Retrieve all metadata and physical asset overrides for a user."""
    return UserService(db).list_user_overrides(user_id)


@router.post("/{user_id}/overrides", response_model=UserOverrideRead)
def create_user_override(user_id: int, override_data: UserOverrideCreate, db: Session = Depends(get_db)):
    """Create or update a user override for a specific media item, performer, or collection."""
    return UserService(db).create_or_update_override(user_id, override_data.model_dump())



# --- Custom User Lists ---

@router.get("/{user_id}/lists", response_model=List[CustomListRead])
def list_user_custom_lists(user_id: int, db: Session = Depends(get_db)):
    """Retrieve custom user lists."""
    return UserService(db).list_user_custom_lists(user_id)


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
from app.infrastructure.tasks.tasks_image_download_adapter import TasksImageDownloadAdapter

def _img_dl():
    return TasksImageDownloadAdapter()

@catalog_router.post("/media/update")
def update_item_overrides(payload: ItemOverridesUpdate, db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).update_item_overrides(payload)

@catalog_router.post("/item/{item_id}/status")
def update_item_status(item_id: str, payload: ItemStatusUpdate, db: Session = Depends(get_db)):
    return UserService(db).update_item_status_composite(
        item_id=item_id,
        payload_data=payload.model_dump(),
        model_fields_set=payload.model_fields_set,
        resolver=DbMediaResolver(db),
    )

@catalog_router.post("/item/{item_id}/poster")
def update_item_poster(item_id: str, payload: ImageOverrideUpdate, db: Session = Depends(get_db)):
    path = payload.path or payload.url or payload.poster_path
    if not path:
        raise HTTPException(status_code=400, detail="Image path/url is required")
    return OverridesService(db, DbMediaResolver(db), image_downloader=_img_dl()).update_item_image(item_id, "poster", path, media_type=payload.media_type)

@catalog_router.post("/item/{item_id}/backdrop")
def update_item_backdrop(item_id: str, payload: ImageOverrideUpdate, db: Session = Depends(get_db)):
    path = payload.path or payload.url or payload.backdrop_path
    if not path:
        raise HTTPException(status_code=400, detail="Image path/url is required")
    return OverridesService(db, DbMediaResolver(db), image_downloader=_img_dl()).update_item_image(item_id, "backdrop", path, media_type=payload.media_type)

@catalog_router.post("/item/{item_id}/logo")
def update_item_logo(item_id: str, payload: ImageOverrideUpdate, db: Session = Depends(get_db)):
    path = payload.path or payload.url or payload.logo_path
    if not path:
        raise HTTPException(status_code=400, detail="Image path/url is required")
    return OverridesService(db, DbMediaResolver(db), image_downloader=_img_dl()).update_item_image(item_id, "logo", path, media_type=payload.media_type)

@catalog_router.post("/item/{item_id}/upload-poster")
def upload_item_poster(item_id: str, file: UploadFile = File(...), media_type: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).handle_image_upload(item_id, "poster", file.filename, file.file, media_type=media_type)

@catalog_router.post("/item/{item_id}/upload-backdrop")
def upload_item_backdrop(item_id: str, file: UploadFile = File(...), media_type: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).handle_image_upload(item_id, "backdrop", file.filename, file.file, media_type=media_type)

@catalog_router.post("/item/{item_id}/upload-logo")
def upload_item_logo(item_id: str, file: UploadFile = File(...), media_type: Optional[str] = Form(None), db: Session = Depends(get_db)):
    return OverridesService(db, DbMediaResolver(db)).handle_image_upload(item_id, "logo", file.filename, file.file, media_type=media_type)

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

@catalog_router.post("/library/item/{item_id}/peaks")
def add_item_peak(item_id: str, db: Session = Depends(get_db)):
    from app.shared_kernel.user_context import get_current_user_id
    from app.infrastructure.media.db_media_resolver import DbMediaResolver
    from app.domains.history.models import PlaybackPeakLog
    from app.domains.users.models import UserOverride
    
    current_uid = get_current_user_id() or 1
    resolver = DbMediaResolver(db)
    media_item_id, metadata_match_id = resolver.resolve_ids(item_id)
    
    if not media_item_id:
        raise HTTPException(status_code=404, detail="Local media item not found")
        
    video_position = 0
    override = None
    if metadata_match_id:
        override = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            UserOverride.metadata_match_id == metadata_match_id
        ).first()
    if not override and media_item_id:
        override = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            UserOverride.media_item_id == media_item_id
        ).first()
        
    player_time = None
    try:
        import requests
        r = requests.get("http://127.0.0.1:8080/requests/status.json", auth=("", "swaya"), timeout=0.1)
        if r.status_code == 200:
            data = r.json()
            player_time = int(data.get("time", 0))
    except Exception:
        pass

    if player_time is None:
        try:
            import requests
            import re
            r = requests.get("http://127.0.0.1:13579/variables.html", timeout=0.1)
            if r.status_code == 200:
                pos_match = re.search(r'id="position">(\d+)</p>', r.text)
                if pos_match:
                    player_time = int(pos_match.group(1)) // 1000
        except Exception:
            pass

    if player_time is not None and player_time > 0:
        video_position = player_time
    else:
        video_position = 0
        
    peak = PlaybackPeakLog(
        user_id=current_uid,
        media_item_id=media_item_id,
        video_position=video_position
    )
    db.add(peak)
    db.commit()
    
    peaks = db.query(PlaybackPeakLog).filter(
        PlaybackPeakLog.user_id == current_uid,
        PlaybackPeakLog.media_item_id == media_item_id
    ).order_by(PlaybackPeakLog.video_position.asc()).all()
    
    return {
        "peaks_count": len(peaks),
        "peaks_history": [
            {
                "id": p.id,
                "video_position": p.video_position,
                "watched_at": p.created_at.isoformat()
            }
            for p in peaks
        ]
    }

@catalog_router.delete("/library/item/{item_id}/peaks/{log_id}")
def delete_item_peak(item_id: str, log_id: int, db: Session = Depends(get_db)):
    from app.shared_kernel.user_context import get_current_user_id
    from app.infrastructure.media.db_media_resolver import DbMediaResolver
    from app.domains.history.models import PlaybackPeakLog
    
    current_uid = get_current_user_id() or 1
    resolver = DbMediaResolver(db)
    media_item_id, _ = resolver.resolve_ids(item_id)
    
    if not media_item_id:
        raise HTTPException(status_code=404, detail="Local media item not found")
        
    peak = db.query(PlaybackPeakLog).filter(
        PlaybackPeakLog.id == log_id,
        PlaybackPeakLog.user_id == current_uid,
        PlaybackPeakLog.media_item_id == media_item_id
    ).first()
    
    if peak:
        db.delete(peak)
        db.commit()
        
    peaks = db.query(PlaybackPeakLog).filter(
        PlaybackPeakLog.user_id == current_uid,
        PlaybackPeakLog.media_item_id == media_item_id
    ).order_by(PlaybackPeakLog.video_position.asc()).all()
    
    return {
        "peaks_count": len(peaks),
        "peaks_history": [
            {
                "id": p.id,
                "video_position": p.video_position,
                "watched_at": p.created_at.isoformat()
            }
            for p in peaks
        ]
    }