from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import OrderSide, PositionStatus, SignalStatus
from app.models.trading import AppSetting, Position, Signal


def _create_signal(db_session: Session, symbol: str = "BTCUSDT") -> Signal:
    signal = Signal(
        symbol=symbol,
        status=SignalStatus.NEW,
        side=OrderSide.BUY,
        entry_price=Decimal("100.00000000"),
        stop_loss_price=Decimal("95.00000000"),
        take_profit_price=Decimal("110.00000000"),
        risk_amount=Decimal("5.00000000"),
        expires_at=datetime.now(UTC).replace(year=2026, month=7, day=23),
        idempotency_key=f"signal-{symbol}",
        metadata_json={"signal_grade": "A", "signal_score": 90},
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


def test_execution_status_reports_disabled_by_default(client: TestClient) -> None:
    response = client.get("/api/v1/execution/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_enabled"] is False
    assert payload["demo_trading_mode"] is True
    assert payload["executable"] is False
    assert "execution_disabled" in payload["reasons"]


def test_execute_signal_opens_demo_position(client: TestClient, db_session: Session) -> None:
    signal = _create_signal(db_session)
    db_session.add_all(
        [
            AppSetting(
                key="execution_enabled",
                value={"value": True},
                value_type="boolean",
                description="test",
            ),
            AppSetting(
                key="demo_account_balance",
                value={"value": 1000.0},
                value_type="decimal",
                description="test",
            ),
        ]
    )
    db_session.commit()

    response = client.post(f"/api/v1/execution/signals/{signal.id}/execute", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "demo"
    assert payload["reused"] is False
    assert payload["risk_decision"]["status"] == "approved"
    assert payload["order"]["status"] == "filled"
    assert payload["position"]["status"] == "open"
    assert payload["position"]["quantity"] == "2.00000000"


def test_execute_signal_blocks_when_max_open_trades_reached(
    client: TestClient,
    db_session: Session,
) -> None:
    signal = _create_signal(db_session, "ETHUSDT")
    db_session.add_all(
        [
            AppSetting(
                key="execution_enabled",
                value={"value": True},
                value_type="boolean",
                description="test",
            ),
            AppSetting(
                key="maximum_open_trades",
                value={"value": 1},
                value_type="integer",
                description="test",
            ),
            Position(
                symbol="BTCUSDT",
                status=PositionStatus.OPEN,
                side=OrderSide.BUY,
                quantity=Decimal("1.00000000"),
                average_entry_price=Decimal("100.00000000"),
            ),
        ]
    )
    db_session.commit()

    response = client.post(f"/api/v1/execution/signals/{signal.id}/execute", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "maximum_open_trades_reached"


def test_close_position_creates_demo_exit_and_realized_pnl(
    client: TestClient,
    db_session: Session,
) -> None:
    signal = _create_signal(db_session)
    db_session.add_all(
        [
            AppSetting(
                key="execution_enabled",
                value={"value": True},
                value_type="boolean",
                description="test",
            ),
            AppSetting(
                key="demo_account_balance",
                value={"value": 1000.0},
                value_type="decimal",
                description="test",
            ),
        ]
    )
    db_session.commit()

    execute_response = client.post(f"/api/v1/execution/signals/{signal.id}/execute", json={})
    position_id = execute_response.json()["position"]["position_id"]

    close_response = client.post(
        f"/api/v1/execution/positions/{position_id}/close",
        json={"exit_price": 108.0},
    )

    assert close_response.status_code == 200
    payload = close_response.json()
    assert payload["order"]["side"] == "sell"
    assert payload["order"]["status"] == "filled"
    assert payload["position"]["status"] == "closed"
    assert payload["position"]["realized_pnl"] == "16.00000000"


def test_read_positions_returns_execution_positions(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(
        Position(
            symbol="BTCUSDT",
            status=PositionStatus.OPEN,
            side=OrderSide.BUY,
            quantity=Decimal("0.50000000"),
            average_entry_price=Decimal("100.00000000"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("2.00000000"),
            metadata_json={"signal_id": "abc"},
        )
    )
    db_session.commit()

    response = client.get("/api/v1/execution/positions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["signal_id"] == "abc"
    assert payload[0]["status"] == "open"
