from __future__ import annotations

import uuid
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_migration_upgrade_downgrade_upgrade(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    temp_dir = Path(".pytest-local")
    temp_dir.mkdir(exist_ok=True)
    database_path = temp_dir / f"migration-{uuid.uuid4()}.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "app_settings" in inspector.get_table_names()
    assert "positions" in inspector.get_table_names()
    assert "exchange_symbols" in inspector.get_table_names()
    assert "ohlcv_candles" in inspector.get_table_names()
    assert "market_snapshots" in inspector.get_table_names()
    assert "market_data_cycles" in inspector.get_table_names()
    assert "market_regime_snapshots" in inspector.get_table_names()

    command.downgrade(config, "202607210003")
    inspector = inspect(engine)
    assert "exchange_symbols" in inspector.get_table_names()
    assert "market_regime_snapshots" not in inspector.get_table_names()

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert "system_events" in inspector.get_table_names()
    engine.dispose()
    database_path.unlink(missing_ok=True)
