from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import OrderSide, OrderStatus, PositionStatus
from app.models.trading import Order, Position, SystemEvent, TradeJournalEntry

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
        last_synced_at = self._last_synced_at(positions)
        return {
            "summary": {
                "total_positions": len(positions),
                "total_orders": len(orders),
                "total_open_quantity": sum((row.quantity for row in positions), DECIMAL_ZERO),
                "total_unrealized_pnl": sum(
                    (row.unrealized_pnl for row in positions), DECIMAL_ZERO
                ),
                "total_realized_pnl": sum((row.realized_pnl for row in positions), DECIMAL_ZERO),
                "last_synced_at": last_synced_at,
            },
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
        trades = [self._journal_payload(db, row) for row in rows]
        wins = sum(1 for item in trades if item["result"] == "WIN")
        losses = sum(1 for item in trades if item["result"] == "LOSS")
        net_pnl = sum((Decimal(str(item["pnl"])) for item in trades), DECIMAL_ZERO)
        total_trades = len(trades)
        average_pnl = (net_pnl / total_trades) if total_trades > 0 else DECIMAL_ZERO
        win_rate = (
            (Decimal(wins) / Decimal(total_trades)) * Decimal("100")
            if total_trades > 0
            else DECIMAL_ZERO
        )
        return {
            "summary": {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate.quantize(Decimal("0.01")),
                "net_pnl": net_pnl,
                "average_pnl": (
                    average_pnl.quantize(Decimal("0.01")) if total_trades > 0 else DECIMAL_ZERO
                ),
            },
            "trades": trades,
        }

    def telemetry_feed(
        self, db: Session, event_limit: int = 20, journal_limit: int = 10
    ) -> dict[str, object]:
        active = self.list_active_trades(db)
        journal = self.list_trade_journal(db)
        system_events = list(
            db.scalars(
                select(SystemEvent).order_by(SystemEvent.event_at.desc()).limit(event_limit)
            )
        )
        journal_entries = list(
            db.scalars(
                select(TradeJournalEntry)
                .order_by(TradeJournalEntry.entry_at.desc())
                .limit(journal_limit)
            )
        )
        return {
            "summary": active["summary"],
            "recent_system_events": [self._system_event_payload(row) for row in system_events],
            "recent_trade_notes": [self._journal_entry_payload(row) for row in journal_entries],
            "recent_closed_trades": journal["trades"][:journal_limit],
            "active_positions": active["positions"],
            "pending_orders": active["orders"],
        }

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
        metadata = row.metadata_json or {}
        return {
            "id": str(row.id),
            "symbol": row.symbol,
            "direction": "LONG" if self._enum_string(row.side) == OrderSide.BUY.value else "SHORT",
            "type": self._enum_string(row.order_type),
            "price": row.price,
            "quantity": row.quantity,
            "filled_quantity": row.filled_quantity,
            "fee": row.fee,
            "created_at": row.created_at,
            "status": self._enum_string(row.status),
            "mode": str(metadata.get("mode") or "unknown"),
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
        journal_entries = list(
            db.scalars(
                select(TradeJournalEntry)
                .where(TradeJournalEntry.position_id == row.id)
                .order_by(TradeJournalEntry.entry_at.asc())
            )
        )
        duration_minutes = (
            int((row.closed_at - row.opened_at).total_seconds() // 60)
            if row.closed_at is not None and row.opened_at is not None
            else None
        )
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
            "duration_minutes": duration_minutes,
            "signal_grade": signal_metadata.get("signal_grade"),
            "setup_id": signal_metadata.get("setup_id"),
            "exit_reason": metadata.get("last_exit_reason"),
            "mode": str(metadata.get("mode") or "unknown"),
            "journal_entries": [self._journal_entry_payload(item) for item in journal_entries],
        }

    def _journal_entry_payload(self, row: TradeJournalEntry) -> dict[str, object]:
        return {
            "entry_id": str(row.id),
            "entry_type": self._enum_string(row.entry_type),
            "title": row.title,
            "body": row.body,
            "entry_at": row.entry_at,
            "metadata_json": row.metadata_json or {},
        }

    def _system_event_payload(self, row: SystemEvent) -> dict[str, object]:
        return {
            "event_id": str(row.id),
            "level": self._enum_string(row.level),
            "source": row.source,
            "message": row.message,
            "event_at": row.event_at,
            "metadata_json": row.metadata_json or {},
        }

    def _last_synced_at(self, positions: list[Position]) -> datetime | None:
        timestamps = [
            datetime.fromisoformat(str((row.metadata_json or {}).get("last_sync_at")))
            for row in positions
            if (row.metadata_json or {}).get("last_sync_at")
        ]
        if not timestamps:
            return None
        return max(timestamps)

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
