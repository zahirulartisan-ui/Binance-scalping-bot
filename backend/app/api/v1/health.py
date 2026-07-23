from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app import __version__
from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.schemas.health import HealthResponse, HealthStatus
from app.services.execution_service import ExecutionService
from app.services.migration_service import migrations_ready

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
        migration_ready = migrations_ready(bind, settings)
        migration_status = HealthStatus(status="ready" if migration_ready else "not_ready")
    except Exception as exc:  # pragma: no cover - exact driver errors vary
        database_status = HealthStatus(status="error", detail=exc.__class__.__name__)
        migration_status = HealthStatus(status="not_ready", detail="database unavailable")

    # Get execution service status snapshot
    service = ExecutionService(settings)
    snapshot = service.get_status(db)

    # Credential readiness
    has_creds = bool(
        settings.binance_futures_demo_api_key and settings.binance_futures_demo_api_secret
    )
    credential_readiness = "ready" if has_creds else "missing"

    # Endpoint allowlist verification
    from urllib.parse import urlparse

    endpoint_allowlist_status = "verified"
    for url_val in [
        settings.binance_futures_demo_base_url,
        settings.binance_futures_demo_market_data_url,
    ]:
        if not url_val:
            endpoint_allowlist_status = "invalid"
            break
        try:
            parsed = urlparse(url_val)
            if parsed.scheme != "https" or parsed.netloc != "demo-fapi.binance.com":
                endpoint_allowlist_status = "invalid"
                break
        except Exception:
            endpoint_allowlist_status = "invalid"
            break

    # Execution readiness clearly distinguishing three states
    if snapshot.executable:
        execution_readiness = "ready"
    elif database_status.status == "ok":
        execution_readiness = "read_only"
    else:
        execution_readiness = "blocked"

    # Futures Demo environment status
    futures_demo_env_status = (
        "active" if (database_status.status == "ok" and not settings.emergency_stop) else "blocked"
    )

    return HealthResponse(
        application=HealthStatus(status="ok", detail=f"{settings.app_name} {__version__}"),
        database=database_status,
        environment=HealthStatus(status=settings.app_env.value),
        demo_trading=HealthStatus(status="disabled"),  # internal simulation is disabled
        execution=HealthStatus(
            status="enabled"
            if settings.effective_execution_enabled and database_status.status == "ok"
            else "disabled",
            detail=(
                "Execution fails closed when disabled, emergency stopped, or database unavailable."
            ),
        ),
        emergency_stop=HealthStatus(status="active" if settings.emergency_stop else "inactive"),
        migrations=migration_status,
        # New safety metadata
        exchange_scope="Binance",
        product_type="USD-M Futures",
        futures_demo_env_status=futures_demo_env_status,
        endpoint_allowlist_status=endpoint_allowlist_status,
        credential_readiness=credential_readiness,
        execution_enabled=settings.effective_execution_enabled,
        execution_readiness=execution_readiness,
        blocking_reason_codes=snapshot.reasons,
    )
