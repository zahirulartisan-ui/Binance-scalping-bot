from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.settings import LogLevel


class PublicSettings(BaseModel):
    app_name: str
    app_env: str
    api_host: str
    api_port: int
    log_level: str
    allowed_origins: list[str]
    execution_enabled: bool
    demo_trading_mode: bool
    demo_account_balance: float
    scanner_interval_seconds: int
    risk_per_trade: float
    maximum_open_trades: int
    daily_loss_limit: float
    emergency_stop: bool
    position_monitoring_enabled: bool
    position_monitoring_interval_seconds: int
    position_monitoring_price_max_age_seconds: int


class RuntimeSettingsPatch(BaseModel):
    log_level: LogLevel | None = None
    allowed_origins: list[str] | None = None
    execution_enabled: bool | None = None
    demo_trading_mode: bool | None = None
    demo_account_balance: float | None = Field(default=None, gt=0, le=1000000000)
    scanner_interval_seconds: int | None = Field(default=None, ge=5, le=3600)
    risk_per_trade: float | None = Field(default=None, gt=0, le=0.05)
    maximum_open_trades: int | None = Field(default=None, ge=0, le=50)
    daily_loss_limit: float | None = Field(default=None, gt=0, le=0.5)
    emergency_stop: bool | None = None
    position_monitoring_enabled: bool | None = None
    position_monitoring_interval_seconds: int | None = Field(default=None, ge=5, le=300)
    position_monitoring_price_max_age_seconds: int | None = Field(default=None, ge=5, le=600)

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [origin.strip() for origin in value if origin.strip()]
        if not cleaned:
            raise ValueError("allowed_origins cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def fail_closed_for_critical_safety(self) -> RuntimeSettingsPatch:
        if self.emergency_stop and self.execution_enabled:
            raise ValueError("execution_enabled cannot be true while emergency_stop is true")
        return self

    def allowed_updates(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_unset=True)
        if payload.get("emergency_stop") is True:
            payload["execution_enabled"] = False
        if "log_level" in payload and isinstance(payload["log_level"], LogLevel):
            payload["log_level"] = payload["log_level"].value
        return payload
