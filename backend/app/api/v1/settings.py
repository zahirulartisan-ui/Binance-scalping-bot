from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.schemas.settings import PublicSettings, RuntimeSettingsPatch
from app.services.settings_service import get_public_settings, update_runtime_settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=PublicSettings)
def read_settings(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicSettings:
    return PublicSettings.model_validate(get_public_settings(db, settings))


@router.patch("", response_model=PublicSettings)
def patch_settings(
    payload: RuntimeSettingsPatch,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicSettings:
    update_runtime_settings(db, payload.allowed_updates())
    return PublicSettings.model_validate(get_public_settings(db, settings))
