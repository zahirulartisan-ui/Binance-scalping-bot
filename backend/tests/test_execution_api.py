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


def _enable_demo_execution(db_session: Session) -> None:
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


def _open_demo_position(client: TestClient, db_session: Session) -> tuple[Signal, str]:
    signal = _create_signal(db_session)
    _enable_demo_execution(db_session)
    response = client.post(f"/api/v1/execution/signals/{signal.id}/execute", json={})
    assert response.status_code == 200
    return signal, response.json()["position"]["position_id"]


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
    _enable_demo_execution(db_session)

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
    _enable_demo_execution(db_session)
    db_session.add(
        Position(
            symbol="BTCUSDT",
            status=PositionStatus.OPEN,
            side=OrderSide.BUY,
            quantity=Decimal("1.00000000"),
            average_entry_price=Decimal("100.00000000"),
        )
    )
    db_session.add(
        AppSetting(
            key="maximum_open_trades",
            value={"value": 1},
            value_type="integer",
            description="test",
        )
    )
    db_session.commit()

    response = client.post(f"/api/v1/execution/signals/{signal.id}/execute", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "maximum_open_trades_reached"


def test_close_position_creates_demo_exit_and_realized_pnl(
    client: TestClient,
    db_session: Session,
) -> None:
    _, position_id = _open_demo_position(client, db_session)

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


def test_partial_close_reduces_quantity_and_keeps_position_open(
    client: TestClient,
    db_session: Session,
) -> None:
    _, position_id = _open_demo_position(client, db_session)

    response = client.post(
        f"/api/v1/execution/positions/{position_id}/partial-close",
        json={"exit_price": 107.0, "quantity": 0.5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "partial_close"
    assert payload["order"]["quantity"] == "0.50000000"
    assert payload["position"]["status"] == "open"
    assert payload["position"]["quantity"] == "1.50000000"
    assert payload["position"]["realized_pnl"] == "3.50000000"


def test_move_stop_updates_position_metadata_and_event(
    client: TestClient,
    db_session: Session,
) -> None:
    _, position_id = _open_demo_position(client, db_session)

    response = client.post(
        f"/api/v1/execution/positions/{position_id}/move-stop",
        json={"new_stop_price": 101.0, "note": "lock some risk"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "move_stop"
    assert payload["order"] is None
    assert payload["position"]["metadata_json"]["stop_loss_price"] == "101.0"
    assert payload["events"][0]["event_type"] == "stop_updated"


def test_monitor_run_applies_partial_take_profit_and_stop_updates(
    client: TestClient,
    db_session: Session,
) -> None:
    _, position_id = _open_demo_position(client, db_session)

    response = client.post(
        "/api/v1/execution/monitor/run",
        json={"prices": [{"symbol": "BTCUSDT", "price": 113.0}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["checked_count"] == 1
    assert payload["action_count"] == 3
    assert [action["action"] for action in payload["actions"]] == [
        "partial_take_profit",
        "move_stop_to_breakeven",
        "trail_stop",
    ]

    position_response = client.get(f"/api/v1/execution/positions/{position_id}")
    position_payload = position_response.json()
    assert position_payload["quantity"] == "1.00000000"
    assert position_payload["metadata_json"]["partial_take_profit_done"] is True
    assert position_payload["metadata_json"]["break_even_moved"] is True
    assert position_payload["metadata_json"]["trailing_stop_active"] is True


def test_monitor_run_closes_position_when_stop_is_hit(
    client: TestClient,
    db_session: Session,
) -> None:
    _, position_id = _open_demo_position(client, db_session)
    client.post(
        f"/api/v1/execution/positions/{position_id}/move-stop",
        json={"new_stop_price": 102.0},
    )

    response = client.post(
        "/api/v1/execution/monitor/run",
        json={"prices": [{"symbol": "BTCUSDT", "price": 101.0}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action_count"] == 1
    assert payload["actions"][0]["action"] == "stop_loss_close"
    assert payload["actions"][0]["position"]["status"] == "closed"


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


def test_read_position_events_returns_execution_history(
    client: TestClient,
    db_session: Session,
) -> None:
    _, position_id = _open_demo_position(client, db_session)

    response = client.get(f"/api/v1/execution/positions/{position_id}/events")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["event_type"] == "opened"
