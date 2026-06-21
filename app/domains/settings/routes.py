from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.shared_kernel.database import get_db
from app.application.maintenance.database_maintenance_service import DatabaseMaintenanceService
from app.domains.settings.models import SystemSetting, UserSetting
from app.domains.settings.services.settings_service import SettingsService
from app.domains.settings.schemas import (
    SystemSettingRead,
    SystemSettingUpdate,
    UserSettingRead,
    UserSettingUpdate,
)

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


# --- System Settings Endpoints ---
@router.get("/system", response_model=List[SystemSettingRead])
def list_system_settings(db: Session = Depends(get_db)):
    """Retrieve all system settings."""
    return db.query(SystemSetting).all()


@router.put("/system/{key}", response_model=SystemSettingRead)
def update_system_setting(key: str, update_data: SystemSettingUpdate, db: Session = Depends(get_db)):
    """Update a specific system setting."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        # Create a new setting if it does not exist
        setting = SystemSetting(key=key, value=update_data.value, description=update_data.description)
        db.add(setting)
    else:
        setting.value = update_data.value
        if update_data.description is not None:
            setting.description = update_data.description
    db.commit()
    db.refresh(setting)
    return setting


# --- User Settings Endpoints ---
@router.get("/user/{user_id}", response_model=List[UserSettingRead])
def list_user_settings(user_id: int, db: Session = Depends(get_db)):
    """Retrieve settings/preferences for a specific user."""
    return db.query(UserSetting).filter(UserSetting.user_id == user_id).all()


@router.put("/user/{user_id}/{key}", response_model=UserSettingRead)
def update_user_setting(user_id: int, key: str, update_data: UserSettingUpdate, db: Session = Depends(get_db)):
    """Update a preference key for a specific user."""
    setting = db.query(UserSetting).filter(UserSetting.user_id == user_id, UserSetting.key == key).first()
    if not setting:
        setting = UserSetting(user_id=user_id, key=key, value=update_data.value, description=update_data.description)
        db.add(setting)
    else:
        setting.value = update_data.value
        if update_data.description is not None:
            setting.description = update_data.description
    db.commit()
    db.refresh(setting)
    return setting
@router.post("/user/{user_id}/avatar")
def upload_user_avatar(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        return SettingsService(db, user_id=user_id).upload_avatar(file.filename or "", file.file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


# --- Combined/Generic Settings Endpoints ---
@router.get("", response_model=dict)
def get_settings(db: Session = Depends(get_db)):
    """Retrieve all user settings as a key-value dictionary."""
    return SettingsService(db, user_id=1).get_settings()


@router.post("", response_model=dict)
def update_settings(payload: dict, db: Session = Depends(get_db)):
    """Update user settings keys."""
    return SettingsService(db, user_id=1).update_settings(payload)


@router.post("/import", response_model=dict)
def import_settings(payload: dict, db: Session = Depends(get_db)):
    """Import and apply settings payload."""
    return SettingsService(db, user_id=1).update_settings(payload)


# --- Validation Endpoints ---
@router.post("/validate-folders", response_model=dict)
def validate_folders(payload: dict, db: Session = Depends(get_db)):
    """Validate scan and library directory paths."""
    return SettingsService(db, user_id=1).validate_folders(payload)


@router.post("/validate-api-keys", response_model=dict)
def validate_api_keys(payload: dict, db: Session = Depends(get_db)):
    """Validate external scraper API keys."""
    return SettingsService(db, user_id=1).validate_api_keys(payload)


@router.get("/changelog", response_model=dict)
def get_changelog(db: Session = Depends(get_db)):
    return SettingsService(db, user_id=1).get_changelog()


@router.get("/ignored-items", response_model=dict)
def get_ignored_items(
    search: str = "",
    offset: int = 0,
    limit: int = 40,
    db: Session = Depends(get_db),
):
    return SettingsService(db, user_id=1).get_ignored_items(search, offset, limit)


class RestoreIgnoredRequest(BaseModel):
    item_ids: List[int]


@router.post("/ignored-items/restore", response_model=dict)
def restore_ignored_items(request: RestoreIgnoredRequest, db: Session = Depends(get_db)):
    return SettingsService(db, user_id=1).restore_ignored_items(request.item_ids)

# --- Database Endpoints ---
db_router = APIRouter(prefix="/api/v1/database", tags=["Database"])

@db_router.post("/clear", response_model=dict)
def clear_database(payload: Optional[dict] = None, db: Session = Depends(get_db)):
    """Clear metadata, files, libraries, or history from database."""
    return DatabaseMaintenanceService(db).clear_database(payload)

