from collections.abc import Generator

import app.models  # noqa: F401
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.settings import AppEnvironment, get_settings
from app.database.base import Base

settings = get_settings()


def _build_engine():
    database_url = str(settings.database_url)
    engine_kwargs: dict[str, object] = {"pool_pre_ping": True}

    # Local test-mode startup should not require a running PostgreSQL instance.
    if settings.app_env is AppEnvironment.TEST and not database_url.startswith("sqlite"):
        database_url = "sqlite+pysqlite:///./test_runtime.db"

    if database_url.startswith("sqlite"):
        engine_kwargs = {"connect_args": {"check_same_thread": False}}
        if database_url.endswith(":memory:"):
            engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(database_url, **engine_kwargs)

    if settings.app_env is AppEnvironment.TEST:
        Base.metadata.create_all(engine)

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_database_connectivity() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
