from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import AppEnvironment, Settings, StrategyMode


def test_approved_futures_demo_url_accepted() -> None:
    # 1. Approved Futures Demo URL is accepted
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
        binance_futures_demo_base_url="https://demo-fapi.binance.com",
        binance_futures_demo_market_data_url="https://demo-fapi.binance.com",
    )
    assert settings.binance_futures_demo_base_url == "https://demo-fapi.binance.com"


def test_binance_spot_url_rejected() -> None:
    # 2. Binance Spot URL is rejected
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            binance_futures_demo_base_url="https://api.binance.com",
        )
    assert "netloc must be demo-fapi.binance.com" in str(exc.value)


def test_binance_production_futures_url_rejected() -> None:
    # 3. Binance production Futures URL is rejected
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            binance_futures_demo_base_url="https://fapi.binance.com",
        )
    assert "netloc must be demo-fapi.binance.com" in str(exc.value)


def test_arbitrary_custom_host_rejected() -> None:
    # 4. Arbitrary custom host is rejected
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            binance_futures_demo_base_url="https://arbitrary.com",
        )
    assert "netloc must be demo-fapi.binance.com" in str(exc.value)


def test_http_trading_url_rejected() -> None:
    # 5. HTTP trading URL is rejected
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            binance_futures_demo_base_url="http://demo-fapi.binance.com",
        )
    assert "must use HTTPS" in str(exc.value)


def test_execution_defaults_off() -> None:
    # 6. Execution defaults OFF
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
    )
    assert settings.execution_enabled is False


def test_emergency_stop_blocks_execution_readiness() -> None:
    # 7. Emergency stop blocks execution readiness
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            execution_enabled=True,
            emergency_stop=True,
            binance_futures_demo_api_key="key",
            binance_futures_demo_api_secret="secret",
        )
    assert "EMERGENCY_STOP" in str(exc.value)


def test_missing_demo_credentials_block_execution_enabled() -> None:
    # 8. Missing Demo credentials block execution readiness when enabled
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            execution_enabled=True,
            binance_futures_demo_api_key=None,
        )
    assert "credentials are required" in str(exc.value)


def test_missing_credentials_allow_readonly_startup() -> None:
    # 9. Missing credentials allow read-only startup when execution is disabled
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
        execution_enabled=False,
        binance_futures_demo_api_key=None,
    )
    assert settings.binance_futures_demo_api_key is None


def test_unsupported_trading_mode_rejected() -> None:
    # 10. Unsupported trading mode is rejected
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env=AppEnvironment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            strategy_supported_trading_mode=StrategyMode.SPOT_LONG_ONLY,
        )
    assert "Spot trading is unsupported" in str(exc.value)


def test_secrets_redacted_from_serialization() -> None:
    # 11. Secrets are redacted from serialization
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
        binance_futures_demo_api_key="futures-demo-secret-key",
        binance_futures_demo_api_secret="futures-demo-secret-secret",
    )
    dumped = settings.model_dump()
    assert dumped["binance_futures_demo_api_key"] == "********"
    assert dumped["binance_futures_demo_api_secret"] == "********"
    assert "futures-demo-secret-key" not in str(dumped)
    assert "futures-demo-secret-secret" not in str(dumped)


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


def test_settings_accepts_comma_separated_and_json_list_env_values() -> None:
    comma_settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins="https://a.example,https://b.example",
        market_data_symbols="BTCUSDT,ethusdt",
    )
    json_settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins='["https://a.example","https://b.example"]',
        market_data_symbols='["BTCUSDT","ethusdt"]',
    )

    assert comma_settings.allowed_origins == ["https://a.example", "https://b.example"]
    assert comma_settings.market_data_symbols == ["BTCUSDT", "ETHUSDT"]
    assert json_settings.allowed_origins == ["https://a.example", "https://b.example"]
    assert json_settings.market_data_symbols == ["BTCUSDT", "ETHUSDT"]
