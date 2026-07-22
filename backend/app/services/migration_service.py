from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

from alembic import command
from app.core.settings import Settings


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_alembic_config(settings: Settings) -> Config:
    backend_root = _backend_root()
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", str(settings.database_url))
    return config


def apply_migrations(settings: Settings) -> None:
    command.upgrade(build_alembic_config(settings), "head")


def migrations_ready(engine: Engine, settings: Settings) -> bool:
    if not inspect(engine).has_table("alembic_version"):
        return False

    with engine.connect() as connection:
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()

    head = ScriptDirectory.from_config(build_alembic_config(settings)).get_current_head()
    return current == head
