from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import OrderStatus, PositionStatus, SignalStatus
from app.models.market_data import ExchangeSymbol
from app.models.trading import Fill, Position, Signal
from app.services.execution_service import ExecutionService


class FakeTradingClient:
    def __init__(self) -> None:
        self.create_payload: dict[str, Any] = {
            "orderId": "9001",
            "clientOrderId": "live-entry-1",
            "status": "NEW",
            "executedQty": "0.00000000",
            "fills": [],
        }
        self.order_payload: dict[str, Any] = {
            "orderId": "9001",
            "status": "FILLED",
            "executedQty": "2.00000000",
            "price": "100.00000000",
        }
        self.trade_payload = [
            {
                "id": "trade-1",
                "price": "100.00000000",
                "qty": "2.00000000",
                "commission": "0.05000000",
                "commissionAsset": "USDT",
                "time": int(datetime.now(UTC).timestamp() * 1000),
            }
        ]
        self.created_orders: list[dict[str, str | None]] = []

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
        self.created_orders.append(
            {
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "client_order_id": client_order_id,
                "price": price,
                "time_in_force": time_in_force,
            }
        )
        payload = dict(self.create_payload)
        payload["clientOrderId"] = client_order_id
        return payload

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, object]:
        return dict(self.order_payload)

    def get_my_trades(
        self,
        symbol: str,
        order_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return [dict(row) for row in self.trade_payload]


def _create_signal(db_session: Session) -> Signal:
    signal = Signal(
        symbol="BTCUSDT",
        status=SignalStatus.NEW,
        side="buy",
        entry_price=Decimal("100.00000000"),
        stop_loss_price=Decimal("95.00000000"),
        take_profit_price=Decimal("110.00000000"),
        risk_amount=Decimal("5.00000000"),
        expires_at=datetime.now(UTC),
        idempotency_key="live-signal",
        metadata_json={"signal_grade": "A"},
    )
    db_session.add(signal)
    db_session.add(
        ExchangeSymbol(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            trading_status="TRADING",
            tick_size=Decimal("0.0100000000"),
            step_size=Decimal("0.0010000000"),
            minimum_quantity=Decimal("0.0010000000"),
            minimum_notional=Decimal("10.0000000000"),
            price_precision=2,
            quantity_precision=3,
        )
    )
    db_session.commit()
    db_session.refresh(signal)
    return signal


def _live_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        execution_enabled=True,
        demo_trading_mode=False,
        binance_api_key="live-key",
        binance_api_secret="live-secret",
    )


def test_live_execute_signal_submits_exchange_order(db_session: Session) -> None:
    signal = _create_signal(db_session)
    client = FakeTradingClient()
    service = ExecutionService(_live_settings(), trading_client=client)  # type: ignore[arg-type]

    result = service.execute_signal(db_session, signal.id)

    assert result.order.status == OrderStatus.ACKNOWLEDGED
    assert result.order.metadata_json["mode"] == "live"
    assert result.position.metadata_json["mode"] == "live"
    assert result.position.quantity == Decimal("0")
    assert client.created_orders[0]["symbol"] == "BTCUSDT"


def test_sync_live_orders_imports_fills_and_updates_position(db_session: Session) -> None:
    signal = _create_signal(db_session)
    client = FakeTradingClient()
    service = ExecutionService(_live_settings(), trading_client=client)  # type: ignore[arg-type]
    service.execute_signal(db_session, signal.id)

    result = service.sync_live_orders(db_session)

    assert result.checked_orders == 1
    assert result.updated_orders == 1
    assert result.new_fills == 1
    position = db_session.scalar(select(Position).where(Position.symbol == "BTCUSDT"))
    assert position is not None
    assert position.status == PositionStatus.OPEN
    assert position.quantity == Decimal("2.00000000")
    fill = db_session.scalar(select(Fill).where(Fill.exchange_trade_id == "trade-1"))
    assert fill is not None


def test_sync_live_orders_closes_unfilled_canceled_entry(db_session: Session) -> None:
    signal = _create_signal(db_session)
    client = FakeTradingClient()
    client.order_payload = {
        "orderId": "9001",
        "status": "CANCELED",
        "executedQty": "0.00000000",
        "price": "100.00000000",
    }
    client.trade_payload = []
    service = ExecutionService(_live_settings(), trading_client=client)  # type: ignore[arg-type]
    service.execute_signal(db_session, signal.id)

    result = service.sync_live_orders(db_session)

    assert result.closed_positions == 1
    position = db_session.scalar(select(Position).where(Position.symbol == "BTCUSDT"))
    assert position is not None
    assert position.status == PositionStatus.CLOSED
    assert position.metadata_json["last_exit_reason"] == "entry_unfilled"
