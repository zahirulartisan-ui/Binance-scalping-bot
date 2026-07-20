from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import MarketDataCycleStatus
from app.models.market_data import MarketDataCycle
from app.services.market_data_runner import MarketDataRunner


class FakeClient:
    def exchange_info(self) -> dict[str, object]:
        return {"symbols": []}

    def recent_price(self, symbol: str) -> dict[str, str]:
        return {"price": "10"}

    def book_ticker(self, symbol: str) -> dict[str, str]:
        return {"bidPrice": "9", "askPrice": "11", "bidQty": "1", "askQty": "1"}

    def klines(self, symbol: str, interval: str, limit: int = 2) -> list[list[object]]:
        now = datetime.now(UTC) - timedelta(minutes=5)
        open_ms = int(now.timestamp() * 1000)
        close_ms = int((now + timedelta(minutes=1) - timedelta(milliseconds=1)).timestamp() * 1000)
        return [[open_ms, "10", "11", "9", "10", "1", close_ms, "10", 1, "1", "10", "0"]]


def test_runner_overlap_prevention(db_session: Session) -> None:
    settings = Settings(app_env="test", database_url="sqlite+pysqlite:///:memory:")
    runner = MarketDataRunner(settings, lambda: db_session, FakeClient())  # type: ignore[arg-type]

    assert runner._cycle_lock.acquire(blocking=False) is True
    try:
        assert runner.run_once() is False
    finally:
        runner._cycle_lock.release()


def test_runner_partial_cycle_failure_reporting(db_session: Session) -> None:
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        market_data_symbols=["BTCUSDT"],
    )
    runner = MarketDataRunner(settings, lambda: db_session, FakeClient())  # type: ignore[arg-type]

    assert runner.run_once() is True
    cycle = db_session.query(MarketDataCycle).first()

    assert cycle is not None
    assert cycle.status == MarketDataCycleStatus.FAILED
    assert cycle.symbols_failed == 1
    assert cycle.rejection_reasons == {"BTCUSDT": "MarketDataValidationError"}


def test_runner_graceful_shutdown(db_session: Session) -> None:
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        market_data_collection_enabled=True,
        market_data_cycle_interval_seconds=10,
    )
    runner = MarketDataRunner(settings, lambda: db_session, FakeClient())  # type: ignore[arg-type]

    runner.start()
    time.sleep(0.01)
    runner.stop()

    assert not runner.is_running
