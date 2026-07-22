from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_serializer, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StrategyMode(StrEnum):
    SPOT_LONG_ONLY = "spot_long_only"


class EvidenceMode(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    DISABLED = "disabled"


class Settings(BaseSettings):
    app_name: str = "Binance Scalping Bot"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: LogLevel = LogLevel.INFO
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/binance_scalping_bot"
    allowed_origins: list[str] = ["http://localhost:5173"]
    binance_demo_api_key: SecretStr | None = None
    binance_demo_api_secret: SecretStr | None = None
    execution_enabled: bool = False
    demo_trading_mode: bool = True
    demo_account_balance: float = Field(default=1000.0, gt=0, le=1000000000)
    scanner_interval_seconds: int = Field(default=30, ge=5, le=3600)
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.05)
    maximum_open_trades: int = Field(default=3, ge=0, le=50)
    daily_loss_limit: float = Field(default=0.03, gt=0, le=0.5)
    emergency_stop: bool = False
    binance_market_data_base_url: str = "https://api.binance.com"
    binance_market_data_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    binance_market_data_max_retries: int = Field(default=2, ge=0, le=5)
    binance_market_data_backoff_seconds: float = Field(default=0.25, ge=0, le=5)
    market_data_collection_enabled: bool = False
    market_data_symbol_refresh_seconds: int = Field(default=3600, ge=60, le=86400)
    market_data_cycle_interval_seconds: int = Field(default=60, ge=10, le=3600)
    market_data_symbols: list[str] = ["BTCUSDT", "ETHUSDT"]
    regime_minimum_candles: int = Field(default=60, ge=20, le=500)
    regime_trend_strength_threshold: float = Field(default=20.0, ge=1, le=100)
    regime_atr_percent_min: float = Field(default=0.02, ge=0, le=10)
    regime_atr_percent_max: float = Field(default=2.5, ge=0.01, le=50)
    regime_realized_volatility_max: float = Field(default=3.0, ge=0.01, le=100)
    regime_abnormal_candle_percent: float = Field(default=5.0, ge=0.1, le=100)
    regime_volume_spike_multiplier: float = Field(default=4.0, ge=1, le=100)
    regime_max_spread_bps: float = Field(default=15.0, ge=0.1, le=1000)
    regime_ema_slope_threshold: float = Field(default=0.001, ge=0, le=10)
    regime_range_compression_threshold: float = Field(default=1.0, ge=0.01, le=50)
    regime_btc_block_volatility_percent: float = Field(default=3.0, ge=0.1, le=100)
    regime_cache_seconds: int = Field(default=30, ge=1, le=3600)
    strategy_enabled: bool = True
    strategy_version: str = "trend-pullback-v1"
    strategy_supported_trading_mode: StrategyMode = StrategyMode.SPOT_LONG_ONLY
    strategy_entry_timeframe: str = "1m"
    strategy_confirmation_timeframe: str = "5m"
    strategy_context_timeframe: str = "15m"
    strategy_minimum_candle_history: int = Field(default=80, ge=50, le=500)
    strategy_ema_fast_period: int = Field(default=20, ge=2, le=100)
    strategy_ema_mid_period: int = Field(default=50, ge=5, le=200)
    strategy_ema_slow_period: int = Field(default=200, ge=50, le=500)
    strategy_ema_slope_lookback: int = Field(default=5, ge=1, le=50)
    strategy_minimum_bullish_ema_slope: float = Field(default=0.001, ge=0, le=10)
    strategy_minimum_impulse_percent: float = Field(default=0.35, gt=0, le=20)
    strategy_impulse_lookback: int = Field(default=20, ge=5, le=100)
    strategy_minimum_pullback_percent: float = Field(default=0.08, gt=0, le=10)
    strategy_maximum_pullback_percent: float = Field(default=1.2, gt=0, le=20)
    strategy_maximum_pullback_candles: int = Field(default=12, ge=2, le=60)
    strategy_maximum_distance_from_ema20_percent: float = Field(default=0.35, ge=0, le=10)
    strategy_maximum_distance_from_ema50_percent: float = Field(default=0.75, ge=0, le=10)
    strategy_entry_zone_atr_tolerance: float = Field(default=0.25, ge=0, le=5)
    strategy_minimum_rejection_body_ratio: float = Field(default=0.45, ge=0, le=1)
    strategy_minimum_rejection_wick_ratio: float = Field(default=0.25, ge=0, le=1)
    strategy_volume_lookback: int = Field(default=20, ge=5, le=100)
    strategy_minimum_recovery_volume_ratio: float = Field(default=1.2, ge=0, le=20)
    strategy_pullback_volume_contraction_threshold: float = Field(default=0.95, ge=0, le=5)
    strategy_liquidity_sweep_mode: EvidenceMode = EvidenceMode.OPTIONAL
    strategy_liquidity_sweep_lookback: int = Field(default=12, ge=3, le=100)
    strategy_minimum_sweep_depth_percent: float = Field(default=0.03, ge=0, le=5)
    strategy_mss_mode: EvidenceMode = EvidenceMode.OPTIONAL
    strategy_mss_swing_lookback: int = Field(default=8, ge=3, le=100)
    strategy_minimum_mss_break_percent: float = Field(default=0.03, ge=0, le=5)
    strategy_stop_loss_atr_buffer: float = Field(default=0.2, ge=0, le=5)
    strategy_minimum_stop_percent: float = Field(default=0.05, gt=0, le=10)
    strategy_maximum_stop_percent: float = Field(default=1.25, gt=0, le=20)
    strategy_minimum_reward_to_risk: float = Field(default=1.5, ge=1, le=10)
    strategy_maximum_setup_age_seconds: int = Field(default=900, ge=60, le=86400)
    strategy_maximum_price_distance_after_zone_percent: float = Field(default=0.6, ge=0, le=10)
    strategy_maximum_spread_bps: float = Field(default=12.0, ge=0, le=1000)
    strategy_cache_ttl_seconds: int = Field(default=15, ge=1, le=3600)
    strategy_persistence_enabled: bool = True
    strategy_signal_grade_a_min: int = Field(default=85, ge=1, le=100)
    strategy_signal_grade_b_min: int = Field(default=70, ge=1, le=100)
    strategy_signal_grade_c_min: int = Field(default=55, ge=1, le=100)
    position_break_even_trigger_rr: float = Field(default=1.0, ge=0.1, le=20)
    position_partial_take_profit_rr: float = Field(default=2.0, ge=0.1, le=20)
    position_partial_take_profit_fraction: float = Field(default=0.5, gt=0, lt=1)
    position_trailing_stop_trigger_rr: float = Field(default=2.5, ge=0.1, le=50)
    position_trailing_stop_buffer_rr: float = Field(default=0.75, ge=0.05, le=10)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("ALLOWED_ORIGINS JSON value must be a list")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("market_data_symbols", mode="before")
    @classmethod
    def parse_market_data_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("MARKET_DATA_SYMBOLS JSON value must be a list")
                return [str(symbol).strip().upper() for symbol in parsed if str(symbol).strip()]
            return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
        return [symbol.upper() for symbol in value]

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+psycopg://", 1)
        elif value.startswith("postgresql://") and "+psycopg" not in value:
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        if "://" in value and ("username:password" in value or "changeme" in value.lower()):
            raise ValueError("DATABASE_URL must not contain placeholder credentials")
        return value

    @model_validator(mode="after")
    def validate_safe_startup(self) -> Settings:
        if self.emergency_stop and self.execution_enabled:
            raise ValueError("execution cannot be enabled while EMERGENCY_STOP is true")

        if self.app_env is not AppEnvironment.TEST and not self.database_url.startswith(
            ("postgresql+psycopg://", "postgresql://")
        ):
            raise ValueError("DATABASE_URL must be a PostgreSQL SQLAlchemy URL outside test mode")

        if self.app_env is AppEnvironment.PRODUCTION:
            if self.execution_enabled:
                raise ValueError("execution must remain disabled in production for V1")
            if self.demo_trading_mode:
                raise ValueError("production mode cannot run with DEMO_TRADING_MODE enabled")
            if any(origin == "*" for origin in self.allowed_origins):
                raise ValueError("production mode cannot allow wildcard CORS origins")
            if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
                raise ValueError("production mode cannot use a local database URL")
        if self.strategy_entry_timeframe != "1m":
            raise ValueError("trend pullback strategy entry timeframe must be 1m")
        if self.strategy_confirmation_timeframe != "5m":
            raise ValueError("trend pullback strategy confirmation timeframe must be 5m")
        if self.strategy_context_timeframe != "15m":
            raise ValueError("trend pullback strategy context timeframe must be 15m")
        if self.strategy_ema_fast_period >= self.strategy_ema_mid_period:
            raise ValueError("strategy EMA fast period must be below mid period")
        if self.strategy_ema_mid_period >= self.strategy_ema_slow_period:
            raise ValueError("strategy EMA mid period must be below slow period")
        if self.strategy_minimum_pullback_percent >= self.strategy_maximum_pullback_percent:
            raise ValueError("strategy minimum pullback must be below maximum pullback")
        if self.strategy_minimum_stop_percent >= self.strategy_maximum_stop_percent:
            raise ValueError("strategy minimum stop must be below maximum stop")
        if not (
            self.strategy_signal_grade_a_min
            > self.strategy_signal_grade_b_min
            > self.strategy_signal_grade_c_min
        ):
            raise ValueError("strategy signal grade thresholds must descend A > B > C")
        return self

    @field_serializer("binance_demo_api_key", "binance_demo_api_secret")
    def serialize_secret(self, value: SecretStr | None) -> str | None:
        if value is None:
            return None
        return "********"

    @property
    def effective_execution_enabled(self) -> bool:
        return self.execution_enabled and not self.emergency_stop

    def public_runtime_defaults(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "app_env": self.app_env.value,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "log_level": self.log_level.value,
            "allowed_origins": self.allowed_origins,
            "execution_enabled": self.effective_execution_enabled,
            "demo_trading_mode": self.demo_trading_mode,
            "demo_account_balance": self.demo_account_balance,
            "scanner_interval_seconds": self.scanner_interval_seconds,
            "risk_per_trade": self.risk_per_trade,
            "maximum_open_trades": self.maximum_open_trades,
            "daily_loss_limit": self.daily_loss_limit,
            "emergency_stop": self.emergency_stop,
            "market_data_collection_enabled": self.market_data_collection_enabled,
            "market_data_symbol_refresh_seconds": self.market_data_symbol_refresh_seconds,
            "market_data_cycle_interval_seconds": self.market_data_cycle_interval_seconds,
            "market_data_symbols": self.market_data_symbols,
            "regime_minimum_candles": self.regime_minimum_candles,
            "regime_cache_seconds": self.regime_cache_seconds,
            "strategy_enabled": self.strategy_enabled,
            "strategy_version": self.strategy_version,
            "strategy_supported_trading_mode": self.strategy_supported_trading_mode.value,
            "strategy_entry_timeframe": self.strategy_entry_timeframe,
            "strategy_confirmation_timeframe": self.strategy_confirmation_timeframe,
            "strategy_context_timeframe": self.strategy_context_timeframe,
            "strategy_minimum_reward_to_risk": self.strategy_minimum_reward_to_risk,
            "strategy_persistence_enabled": self.strategy_persistence_enabled,
            "strategy_signal_grade_a_min": self.strategy_signal_grade_a_min,
            "strategy_signal_grade_b_min": self.strategy_signal_grade_b_min,
            "strategy_signal_grade_c_min": self.strategy_signal_grade_c_min,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
