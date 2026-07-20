from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    application: HealthStatus
    database: HealthStatus
    execution: HealthStatus
