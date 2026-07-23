from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app import __version__
from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.schemas.health import (
    EndpointSafetyStatus,
    ExecutionSafetyStatus,
    HealthResponse,
    HealthStatus,
)
from app.services.migration_service import migrations_ready

router = APIRouter()

FUTURES_DEMO_ALLOWLISTED_HOSTS = {"demo-fapi.binance.com"}


def _endpoint_is_allowlisted(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in FUTURES_DEMO_ALLOWLISTED_HOSTS


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    database_status = HealthStatus(status="ok")
    migration_status = HealthStatus(status="unknown")
    migration_ready = False

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

    database_ready = database_status.status == "ok"
    credentials_ready = (
        settings.binance_demo_api_key is not None
        and settings.binance_demo_api_secret is not None
    )
    trading_endpoint_allowlisted = _endpoint_is_allowlisted(settings.binance_trading_base_url)
    market_data_endpoint_allowlisted = _endpoint_is_allowlisted(
        settings.binance_market_data_base_url
    )
    endpoint_safe = trading_endpoint_allowlisted and market_data_endpoint_allowlisted

    blocking_reason_codes: list[str] = []
    if not settings.execution_enabled:
        blocking_reason_codes.append("execution_disabled")
    if settings.emergency_stop:
        blocking_reason_codes.append("emergency_stop_active")
    if not credentials_ready:
        blocking_reason_codes.append("futures_demo_credentials_missing")
    if not endpoint_safe:
        blocking_reason_codes.append("unsafe_exchange_endpoint")
    if not settings.demo_trading_mode:
        blocking_reason_codes.append("unsupported_trading_mode")
    if not database_ready:
        blocking_reason_codes.append("database_not_ready")
    if not migration_ready:
        blocking_reason_codes.append("migrations_not_ready")

    execution_ready = len(blocking_reason_codes) == 0
    if execution_ready:
        execution_status = "ready"
    elif settings.execution_enabled:
        execution_status = "blocked"
    else:
        execution_status = "disabled"

    return HealthResponse(
        application=HealthStatus(status="ok", detail=f"{settings.app_name} {__version__}"),
        database=database_status,
        environment=HealthStatus(status=settings.app_env.value),
        demo_trading=HealthStatus(
            status="enabled" if settings.demo_trading_mode else "disabled",
            detail="Legacy compatibility field; exchange safety is reported separately.",
        ),
        execution=HealthStatus(
            status=execution_status,
            detail="Execution is ready only when every Futures Demo safety gate passes.",
        ),
        emergency_stop=HealthStatus(status="active" if settings.emergency_stop else "inactive"),
        migrations=migration_status,
        exchange_scope=HealthStatus(status="binance"),
        product_type=HealthStatus(status="usd_m_futures", detail="USDT perpetual futures only"),
        trading_environment=HealthStatus(status="futures_demo_only"),
        endpoints=EndpointSafetyStatus(
            trading_base_url=settings.binance_trading_base_url,
            market_data_base_url=settings.binance_market_data_base_url,
            trading_endpoint_allowlisted=trading_endpoint_allowlisted,
            market_data_endpoint_allowlisted=market_data_endpoint_allowlisted,
            allowlisted_hosts=sorted(FUTURES_DEMO_ALLOWLISTED_HOSTS),
        ),
        safety=ExecutionSafetyStatus(
            enabled=settings.execution_enabled,
            ready=execution_ready,
            credentials_ready=credentials_ready,
            endpoint_safe=endpoint_safe,
            database_ready=database_ready,
            migrations_ready=migration_ready,
            emergency_stop_active=settings.emergency_stop,
            blocking_reason_codes=blocking_reason_codes,
        ),
    )
