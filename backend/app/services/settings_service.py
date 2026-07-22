from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import AppSettingValueType
from app.models.trading import AppSetting

RUNTIME_SETTING_TYPES: dict[str, AppSettingValueType] = {
    "log_level": AppSettingValueType.STRING,
    "allowed_origins": AppSettingValueType.JSON,
    "execution_enabled": AppSettingValueType.BOOLEAN,
    "demo_trading_mode": AppSettingValueType.BOOLEAN,
    "demo_account_balance": AppSettingValueType.DECIMAL,
    "scanner_interval_seconds": AppSettingValueType.INTEGER,
    "risk_per_trade": AppSettingValueType.DECIMAL,
    "maximum_open_trades": AppSettingValueType.INTEGER,
    "daily_loss_limit": AppSettingValueType.DECIMAL,
    "emergency_stop": AppSettingValueType.BOOLEAN,
}


def _stored_value(setting: AppSetting) -> Any:
    return setting.value["value"]


def get_public_settings(db: Session, settings: Settings) -> dict[str, Any]:
    public_settings = settings.public_runtime_defaults()
    rows = db.scalars(select(AppSetting).where(AppSetting.key.in_(RUNTIME_SETTING_TYPES))).all()
    for row in rows:
        public_settings[row.key] = _stored_value(row)
    if public_settings["emergency_stop"]:
        public_settings["execution_enabled"] = False
    return public_settings


def update_runtime_settings(db: Session, updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        value_type = RUNTIME_SETTING_TYPES[key]
        setting = db.scalar(select(AppSetting).where(AppSetting.key == key))
        payload = {"value": value}
        if setting is None:
            setting = AppSetting(
                key=key,
                value=payload,
                value_type=value_type,
                description="Runtime configurable application setting.",
            )
            db.add(setting)
        else:
            setting.value = payload
            setting.value_type = value_type
    db.flush()
    return updates
