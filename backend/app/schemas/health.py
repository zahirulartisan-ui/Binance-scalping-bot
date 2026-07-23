from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    application: HealthStatus
    database: HealthStatus
    environment: HealthStatus
    demo_trading: HealthStatus
    execution: HealthStatus
    emergency_stop: HealthStatus
    migrations: HealthStatus

    # New USD-M Futures fields
    exchange_scope: str
    product_type: str
    futures_demo_env_status: str
    endpoint_allowlist_status: str
    credential_readiness: str
    execution_enabled: bool
    execution_readiness: str
    blocking_reason_codes: list[str]
