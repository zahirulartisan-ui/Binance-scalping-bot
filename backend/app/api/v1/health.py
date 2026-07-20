from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.schemas.health import HealthResponse, HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    database_status = HealthStatus(status="ok")
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - exact driver errors vary
        database_status = HealthStatus(status="error", detail=exc.__class__.__name__)

    return HealthResponse(
        application=HealthStatus(status="ok", detail=f"{settings.app_name} {__version__}"),
        database=database_status,
        execution=HealthStatus(
            status="disabled" if not settings.execution_enabled else "enabled",
            detail="Live execution is disabled by default.",
        ),
    )
