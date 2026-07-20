from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import AppEnvironment, Settings


def test_settings_support_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SCANNER_INTERVAL_SECONDS", "60")

    settings = Settings()

    assert settings.app_env is AppEnvironment.TEST
    assert settings.scanner_interval_seconds == 60


def test_production_rejects_unsafe_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env=AppEnvironment.PRODUCTION,
            database_url="postgresql+psycopg://postgres:postgres@localhost:5432/app",
            demo_trading_mode=True,
        )


def test_secret_values_are_redacted() -> None:
    settings = Settings(
        binance_demo_api_key="demo-key",
        binance_demo_api_secret="demo-secret",
    )

    dumped = settings.model_dump()

    assert dumped["binance_demo_api_key"] == "********"
    assert dumped["binance_demo_api_secret"] == "********"
    assert "demo-key" not in str(dumped)
    assert "demo-secret" not in str(dumped)
