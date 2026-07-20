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
