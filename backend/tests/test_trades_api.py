from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import OrderSide, OrderStatus, OrderType, PositionStatus
from app.models.trading import Order, Position


def test_active_trades_api_returns_open_positions(client: TestClient, db_session: Session) -> None:
    position = Position(
        symbol="BTCUSDT",
        status=PositionStatus.OPEN,
        side=OrderSide.BUY,
        quantity=Decimal("0.50000000"),
        average_entry_price=Decimal("100.00000000"),
        realized_pnl=Decimal("1.25000000"),
        unrealized_pnl=Decimal("0.75000000"),
        metadata_json={"stop_loss_price": "95", "take_profit_price": "110"},
    )
    db_session.add(position)
    db_session.commit()

    response = client.get("/api/v1/trades/active")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["positions"]) == 1
    assert payload["positions"][0]["symbol"] == "BTCUSDT"
    assert payload["positions"][0]["direction"] == "LONG"
    assert payload["positions"][0]["stop_loss"] == "95"


def test_trade_journal_api_returns_closed_positions(
    client: TestClient,
    db_session: Session,
) -> None:
    position = Position(
        symbol="ETHUSDT",
        status=PositionStatus.CLOSED,
        side=OrderSide.BUY,
        quantity=Decimal("0"),
        average_entry_price=Decimal("200.00000000"),
        realized_pnl=Decimal("12.50000000"),
        unrealized_pnl=Decimal("0"),
        metadata_json={"initial_stop_loss_price": "190", "take_profit_price": "220"},
    )
    db_session.add(position)
    db_session.flush()
    db_session.add(
        Order(
            position_id=position.id,
            signal_id=None,
            client_order_id="journal-exit-1",
            exchange_order_id="journal-exit-1",
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            price=Decimal("212.50000000"),
            quantity=Decimal("1.00000000"),
            filled_quantity=Decimal("1.00000000"),
            fee=Decimal("0"),
        )
    )
    db_session.commit()

    response = client.get("/api/v1/trades/journal")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["trades"]) == 1
    assert payload["trades"][0]["symbol"] == "ETHUSDT"
    assert payload["trades"][0]["result"] == "WIN"
    assert payload["trades"][0]["risk_reward"] == "1:1.25"
