from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import AppSettingValueType, OrderSide, PositionStatus
from app.models.market_data import MarketSnapshot
from app.models.trading import AppSetting, Position, SystemEvent
from app.services.trade_management_runner import TradeManagementRunner


class FakeClient:
    def __init__(self, price: str = "94") -> None:
        self.price = price
        self.calls: list[str] = []

    def recent_price(self, symbol: str) -> dict[str, str]:
        self.calls.append(symbol)
        return {"price": self.price}


def _demo_position() -> Position:
    return Position(
        symbol="BTCUSDT",
        status=PositionStatus.OPEN,
        side=OrderSide.BUY,
        quantity=Decimal("1.00000000"),
        average_entry_price=Decimal("100.00000000"),
        metadata_json={
            "mode": "demo",
            "signal_id": "demo-signal",
            "stop_loss_price": "95.00000000",
            "initial_stop_loss_price": "95.00000000",
            "take_profit_price": "110.00000000",
            "initial_quantity": "1.00000000",
            "partial_take_profit_done": False,
            "break_even_moved": False,
            "trailing_stop_active": False,
        },
    )


def test_trade_management_runner_uses_fresh_snapshot_prices(db_session: Session) -> None:
    db_session.add(_demo_position())
    db_session.add(
        MarketSnapshot(
            symbol="BTCUSDT",
            last_price=Decimal("94.00000000"),
            bid_price=Decimal("93.90000000"),
            ask_price=Decimal("94.10000000"),
            bid_quantity=Decimal("1.00000000"),
            ask_quantity=Decimal("1.00000000"),
            spread_bps=Decimal("21.27659574"),
            snapshot_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    client = FakeClient(price="120")
    runner = TradeManagementRunner(
        Settings(app_env="test", database_url="sqlite+pysqlite:///:memory:"),
        lambda: db_session,
        client,  # type: ignore[arg-type]
    )

    assert runner.run_once() is True

    position = db_session.scalar(select(Position).where(Position.symbol == "BTCUSDT"))
    assert position is not None
    assert position.status == PositionStatus.CLOSED
    assert client.calls == []


def test_trade_management_runner_falls_back_to_live_quote_when_snapshot_is_stale(
    db_session: Session,
) -> None:
    db_session.add(_demo_position())
    db_session.add(
        MarketSnapshot(
            symbol="BTCUSDT",
            last_price=Decimal("120.00000000"),
            bid_price=Decimal("119.90000000"),
            ask_price=Decimal("120.10000000"),
            bid_quantity=Decimal("1.00000000"),
            ask_quantity=Decimal("1.00000000"),
            spread_bps=Decimal("16.68056714"),
            snapshot_at=datetime.now(UTC) - timedelta(minutes=10),
        )
    )
    db_session.commit()
    client = FakeClient(price="94")
    runner = TradeManagementRunner(
        Settings(app_env="test", database_url="sqlite+pysqlite:///:memory:"),
        lambda: db_session,
        client,  # type: ignore[arg-type]
    )

    assert runner.run_once() is True

    position = db_session.scalar(select(Position).where(Position.symbol == "BTCUSDT"))
    assert position is not None
    assert position.status == PositionStatus.CLOSED
    assert client.calls == ["BTCUSDT"]
    event = db_session.scalars(
        select(SystemEvent).where(SystemEvent.source == "trade_management_runner")
    ).first()
    assert event is not None
    assert event.metadata_json["fallback_quotes"] == ["BTCUSDT"]


def test_trade_management_runner_respects_runtime_disable_flag(db_session: Session) -> None:
    db_session.add(_demo_position())
    db_session.add(
        AppSetting(
            key="position_monitoring_enabled",
            value={"value": False},
            value_type=AppSettingValueType.BOOLEAN,
            description="test",
        )
    )
    db_session.commit()
    client = FakeClient(price="94")
    runner = TradeManagementRunner(
        Settings(app_env="test", database_url="sqlite+pysqlite:///:memory:"),
        lambda: db_session,
        client,  # type: ignore[arg-type]
    )

    assert runner.run_once() is True

    position = db_session.scalar(select(Position).where(Position.symbol == "BTCUSDT"))
    assert position is not None
    assert position.status == PositionStatus.OPEN
    assert client.calls == []


def test_trade_management_runner_graceful_shutdown(db_session: Session) -> None:
    runner = TradeManagementRunner(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
            position_monitoring_interval_seconds=10,
        ),
        lambda: db_session,
        FakeClient(),  # type: ignore[arg-type]
    )

    runner.start()
    time.sleep(0.01)
    runner.stop()

    assert not runner.is_running
