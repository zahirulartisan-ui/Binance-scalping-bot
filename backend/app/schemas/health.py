from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str
    detail: str | None = None


class EndpointSafetyStatus(BaseModel):
    trading_base_url: str
    market_data_base_url: str
    trading_endpoint_allowlisted: bool
    market_data_endpoint_allowlisted: bool
    allowlisted_hosts: list[str] = Field(default_factory=list)


class ExecutionSafetyStatus(BaseModel):
    enabled: bool
    ready: bool
    credentials_ready: bool
    endpoint_safe: bool
    database_ready: bool
    migrations_ready: bool
    emergency_stop_active: bool
    blocking_reason_codes: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    application: HealthStatus
    database: HealthStatus
    environment: HealthStatus
    demo_trading: HealthStatus
    execution: HealthStatus
    emergency_stop: HealthStatus
    migrations: HealthStatus
    exchange_scope: HealthStatus
    product_type: HealthStatus
    trading_environment: HealthStatus
    endpoints: EndpointSafetyStatus
    safety: ExecutionSafetyStatus
