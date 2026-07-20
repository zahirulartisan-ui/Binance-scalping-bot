from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import Engine, inspect, text
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
    migration_status = HealthStatus(status="unknown")
    try:
        db.execute(text("SELECT 1"))
        bind = db.get_bind()
        if not isinstance(bind, Engine):
            raise RuntimeError("database bind is unavailable")
        migration_ready = inspect(bind).has_table("alembic_version")
        migration_status = HealthStatus(status="ready" if migration_ready else "not_ready")
    except Exception as exc:  # pragma: no cover - exact driver errors vary
        database_status = HealthStatus(status="error", detail=exc.__class__.__name__)
        migration_status = HealthStatus(status="not_ready", detail="database unavailable")

    return HealthResponse(
        application=HealthStatus(status="ok", detail=f"{settings.app_name} {__version__}"),
        database=database_status,
        environment=HealthStatus(status=settings.app_env.value),
        demo_trading=HealthStatus(status="enabled" if settings.demo_trading_mode else "disabled"),
        execution=HealthStatus(
            status="enabled"
            if settings.effective_execution_enabled and database_status.status == "ok"
            else "disabled",
            detail=(
                "Execution fails closed when disabled, emergency stopped, "
                "or database unavailable."
            ),
        ),
        emergency_stop=HealthStatus(status="active" if settings.emergency_stop else "inactive"),
        migrations=migration_status,
    )
