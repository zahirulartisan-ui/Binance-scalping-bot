from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.settings import get_settings
from app.database.base import Base
from app.database.session import get_db
from app.main import create_app
from app.services.execution_service import ExecutionService


class FakeDemoTradingClient:
    def __init__(self) -> None:
        self._order_number = 0

    def get_account(self) -> dict[str, object]:
        return {"balances": [{"asset": "USDT", "free": "1000.00000000", "locked": "0.00000000"}]}

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        client_order_id: str,
        price: str | None = None,
        time_in_force: str | None = None,
    ) -> dict[str, object]:
        self._order_number += 1
        fill_price = price or "108.00000000"
        return {
            "orderId": str(self._order_number),
            "clientOrderId": client_order_id,
            "status": "FILLED",
            "executedQty": quantity,
            "cummulativeQuoteQty": str(float(quantity) * float(fill_price)),
            "fills": [
                {
                    "tradeId": f"trade-{self._order_number}",
                    "price": fill_price,
                    "qty": quantity,
                    "commission": "0",
                    "commissionAsset": "USDT",
                }
            ],
        }


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('202607220006')")
        )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("BINANCE_DEMO_API_KEY", "demo-key")
    monkeypatch.setenv("BINANCE_DEMO_API_SECRET", "demo-secret")
    fake_trading_client = FakeDemoTradingClient()
    monkeypatch.setattr(
        ExecutionService,
        "_get_trading_client",
        lambda self: fake_trading_client,
    )
    get_settings.cache_clear()
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
