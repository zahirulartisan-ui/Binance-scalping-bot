from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import OrderSide, OrderStatus, PositionStatus
from app.models.trading import Order, Position

DECIMAL_ZERO = Decimal("0")


class TradesService:
    def list_active_trades(self, db: Session) -> dict[str, list[dict[str, object]]]:
        positions = list(
            db.scalars(
                select(Position)
                .where(Position.status == PositionStatus.OPEN)
                .order_by(Position.opened_at.desc())
            )
        )
        orders = list(
            db.scalars(
                select(Order)
                .where(Order.status.in_([OrderStatus.CREATED, OrderStatus.SUBMITTED]))
                .order_by(Order.created_at.desc())
            )
        )
        return {
            "positions": [self._position_payload(db, row) for row in positions],
            "orders": [self._order_payload(row) for row in orders],
        }

    def list_trade_journal(self, db: Session) -> dict[str, list[dict[str, object]]]:
        rows = list(
            db.scalars(
                select(Position)
                .where(Position.status == PositionStatus.CLOSED)
                .order_by(Position.closed_at.desc(), Position.opened_at.desc())
            )
        )
        return {"trades": [self._journal_payload(db, row) for row in rows]}

    def _position_payload(self, db: Session, row: Position) -> dict[str, object]:
        metadata = row.metadata_json or {}
        current_price = row.average_entry_price
        stop_loss = self._decimal_or_none(metadata.get("stop_loss_price"))
        take_profit = self._decimal_or_none(metadata.get("take_profit_price"))
        latest_exit = db.scalar(
            select(Order)
            .where(Order.position_id == row.id, Order.side == OrderSide.SELL)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        if latest_exit is not None and latest_exit.price is not None:
            current_price = latest_exit.price

        pnl = (current_price - row.average_entry_price) * row.quantity + row.realized_pnl
        return {
            "id": str(row.id),
            "symbol": row.symbol,
            "direction": "LONG" if self._enum_string(row.side) == OrderSide.BUY.value else "SHORT",
            "quantity": row.quantity,
            "entry_price": row.average_entry_price,
            "current_price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "pnl": pnl,
            "opened_at": row.opened_at,
            "status": self._enum_string(row.status),
        }

    def _order_payload(self, row: Order) -> dict[str, object]:
        return {
            "id": str(row.id),
            "symbol": row.symbol,
            "direction": "LONG" if self._enum_string(row.side) == OrderSide.BUY.value else "SHORT",
            "type": self._enum_string(row.order_type),
            "price": row.price,
            "quantity": row.quantity,
            "created_at": row.created_at,
            "status": self._enum_string(row.status),
        }

    def _journal_payload(self, db: Session, row: Position) -> dict[str, object]:
        metadata = row.metadata_json or {}
        signal_id = metadata.get("signal_id")
        signal_metadata: dict[str, object] = {}
        if signal_id is not None:
            signal_order = db.scalar(
                select(Order)
                .where(Order.position_id == row.id, Order.signal_id == uuid.UUID(str(signal_id)))
                .order_by(Order.created_at.asc())
                .limit(1)
            )
            if signal_order is not None and signal_order.signal is not None:
                signal_metadata = signal_order.signal.metadata_json or {}

        exit_order = db.scalar(
            select(Order)
            .where(Order.position_id == row.id, Order.side == OrderSide.SELL)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        exit_price = (
            exit_order.price
            if exit_order and exit_order.price is not None
            else row.average_entry_price
        )
        stop_loss_value = metadata.get("initial_stop_loss_price") or metadata.get("stop_loss_price")
        stop_loss = self._decimal_or_none(stop_loss_value)
        take_profit = self._decimal_or_none(metadata.get("take_profit_price"))
        risk_reward = self._risk_reward(row.average_entry_price, exit_price, stop_loss)
        return {
            "id": str(row.id),
            "symbol": row.symbol,
            "strategy": str(signal_metadata.get("strategy_name") or "Trend Pullback"),
            "direction": "LONG" if self._enum_string(row.side) == OrderSide.BUY.value else "SHORT",
            "entry_price": row.average_entry_price,
            "exit_price": exit_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward": risk_reward,
            "pnl": row.realized_pnl,
            "result": "WIN" if row.realized_pnl >= DECIMAL_ZERO else "LOSS",
            "opened_at": row.opened_at,
            "closed_at": row.closed_at,
        }

    def _risk_reward(
        self,
        entry_price: Decimal,
        exit_price: Decimal,
        stop_loss: Decimal | None,
    ) -> str:
        if stop_loss is None:
            return "N/A"
        risk = entry_price - stop_loss
        if risk <= DECIMAL_ZERO:
            return "N/A"
        reward = exit_price - entry_price
        rr = reward / risk
        return f"1:{rr.quantize(Decimal('0.01'))}"

    def _decimal_or_none(self, value: object) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    def _enum_string(self, value: object) -> str:
        if isinstance(value, str):
            return value
        return str(value.value)
