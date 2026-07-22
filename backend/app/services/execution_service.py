from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.models.enums import (
    JournalEntryType,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionEventType,
    PositionStatus,
    RiskDecisionStatus,
    SignalStatus,
    SystemEventLevel,
)
from app.models.trading import (
    Fill,
    Order,
    Position,
    PositionEvent,
    RiskDecision,
    Signal,
    SystemEvent,
    TradeJournalEntry,
)
from app.services.settings_service import get_public_settings

DECIMAL_ZERO = Decimal("0")
DECIMAL_EIGHT_PLACES = Decimal("0.00000001")


class ExecutionError(Exception):
    pass


class SignalExecutionNotFoundError(ExecutionError):
    pass


class PositionNotFoundError(ExecutionError):
    pass


class ExecutionConflictError(ExecutionError):
    pass


@dataclass(frozen=True)
class ExecutionStatusSnapshot:
    execution_enabled: bool
    demo_trading_mode: bool
    emergency_stop: bool
    demo_account_balance: Decimal
    risk_per_trade: Decimal
    daily_loss_limit: Decimal
    daily_loss_limit_amount: Decimal
    maximum_open_trades: int
    open_positions: int
    realized_pnl_today: Decimal
    executable: bool
    reasons: list[str]


@dataclass(frozen=True)
class ExecutionResult:
    signal: Signal
    risk_decision: RiskDecision
    order: Order
    position: Position
    reused: bool


class ExecutionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_status(self, db: Session) -> ExecutionStatusSnapshot:
        runtime = self._runtime_settings(db)
        open_positions = self._count_open_positions(db)
        realized_pnl_today = self._realized_pnl_today(db)
        daily_loss_limit_amount = (
            runtime["demo_account_balance"] * runtime["daily_loss_limit"]
        ).quantize(DECIMAL_EIGHT_PLACES)
        reasons: list[str] = []
        if not runtime["execution_enabled"]:
            reasons.append("execution_disabled")
        if runtime["emergency_stop"]:
            reasons.append("emergency_stop_active")
        if not runtime["demo_trading_mode"]:
            reasons.append("live_execution_not_supported")
        if open_positions >= runtime["maximum_open_trades"]:
            reasons.append("maximum_open_trades_reached")
        if realized_pnl_today <= -daily_loss_limit_amount:
            reasons.append("daily_loss_limit_reached")

        return ExecutionStatusSnapshot(
            execution_enabled=runtime["execution_enabled"],
            demo_trading_mode=runtime["demo_trading_mode"],
            emergency_stop=runtime["emergency_stop"],
            demo_account_balance=runtime["demo_account_balance"],
            risk_per_trade=runtime["risk_per_trade"],
            daily_loss_limit=runtime["daily_loss_limit"],
            daily_loss_limit_amount=daily_loss_limit_amount,
            maximum_open_trades=runtime["maximum_open_trades"],
            open_positions=open_positions,
            realized_pnl_today=realized_pnl_today,
            executable=len(reasons) == 0,
            reasons=reasons,
        )

    def list_positions(
        self,
        db: Session,
        status: PositionStatus | None = None,
        limit: int = 100,
    ) -> list[Position]:
        statement = select(Position).order_by(Position.opened_at.desc()).limit(limit)
        if status is not None:
            statement = statement.where(Position.status == status)
        return list(db.scalars(statement))

    def get_position(self, db: Session, position_id: uuid.UUID) -> Position | None:
        return db.scalar(select(Position).where(Position.id == position_id))

    def execute_signal(
        self,
        db: Session,
        signal_id: uuid.UUID,
        quantity_override: Decimal | None = None,
        entry_price_override: Decimal | None = None,
        note: str | None = None,
    ) -> ExecutionResult:
        signal = db.scalar(select(Signal).where(Signal.id == signal_id))
        if signal is None:
            raise SignalExecutionNotFoundError("signal not found")

        existing = db.scalar(
            select(Order)
            .where(Order.signal_id == signal.id, Order.position_id.is_not(None))
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        if existing is not None and existing.position is not None:
            risk_decision = self._latest_risk_decision(db, signal.id)
            if risk_decision is None:
                raise ExecutionConflictError("signal already executed")
            return ExecutionResult(
                signal=signal,
                risk_decision=risk_decision,
                order=existing,
                position=existing.position,
                reused=True,
            )

        status = self.get_status(db)
        if not status.executable:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code=status.reasons[0],
                metadata_json={"reasons": status.reasons},
            )
            raise ExecutionConflictError(decision.reason_code)

        signal_status = self._enum_string(signal.status)
        if signal_status not in {SignalStatus.NEW.value, SignalStatus.ACCEPTED.value}:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="signal_not_actionable",
                metadata_json={"signal_status": signal_status},
            )
            raise ExecutionConflictError(decision.reason_code)

        signal_side = self._enum_string(signal.side)
        if signal_side != OrderSide.BUY.value:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="unsupported_signal_side",
                metadata_json={"signal_side": signal_side},
            )
            raise ExecutionConflictError(decision.reason_code)

        entry_price = entry_price_override or signal.entry_price
        stop_loss = signal.stop_loss_price
        if stop_loss is None:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="missing_stop_loss",
                metadata_json={},
            )
            raise ExecutionConflictError(decision.reason_code)

        stop_distance = entry_price - stop_loss
        if entry_price <= DECIMAL_ZERO or stop_distance <= DECIMAL_ZERO:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="invalid_price_or_stop",
                metadata_json={
                    "entry_price": str(entry_price),
                    "stop_loss_price": str(stop_loss),
                },
            )
            raise ExecutionConflictError(decision.reason_code)

        runtime = self._runtime_settings(db)
        risk_budget = (runtime["demo_account_balance"] * runtime["risk_per_trade"]).quantize(
            DECIMAL_EIGHT_PLACES
        )
        quantity = quantity_override or self._quantize(risk_budget / stop_distance)
        if quantity <= DECIMAL_ZERO:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="invalid_order_quantity",
                metadata_json={"risk_budget": str(risk_budget)},
            )
            raise ExecutionConflictError(decision.reason_code)

        now = datetime.now(UTC)
        position = Position(
            symbol=signal.symbol,
            status=PositionStatus.OPEN,
            side=signal.side,
            quantity=quantity,
            average_entry_price=entry_price,
            realized_pnl=DECIMAL_ZERO,
            unrealized_pnl=DECIMAL_ZERO,
            opened_at=now,
            metadata_json={
                "signal_id": str(signal.id),
                "mode": "demo",
                "stop_loss_price": str(stop_loss),
                "take_profit_price": str(signal.take_profit_price)
                if signal.take_profit_price is not None
                else None,
                "note": note,
            },
        )
        db.add(position)
        db.flush()

        decision = self._record_risk_decision(
            db=db,
            signal=signal,
            status=RiskDecisionStatus.APPROVED,
            reason_code="execution_approved",
            metadata_json={
                "mode": "demo",
                "entry_price": str(entry_price),
                "stop_loss_price": str(stop_loss),
                "quantity": str(quantity),
                "risk_budget": str(risk_budget),
            },
        )

        order = Order(
            signal_id=signal.id,
            position_id=position.id,
            client_order_id=f"demo-entry-{signal.id}",
            exchange_order_id=f"demo-entry-{signal.id}",
            symbol=signal.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            price=entry_price,
            quantity=quantity,
            filled_quantity=quantity,
            fee=DECIMAL_ZERO,
            submitted_at=now,
            metadata_json={"mode": "demo", "note": note},
        )
        db.add(order)
        db.flush()

        fill = Fill(
            order_id=order.id,
            exchange_trade_id=f"demo-fill-entry-{order.id}",
            price=entry_price,
            quantity=quantity,
            fee=DECIMAL_ZERO,
            fee_asset="USDT",
            filled_at=now,
            metadata_json={"mode": "demo"},
        )
        event = PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.OPENED,
            quantity_delta=quantity,
            price=entry_price,
            realized_pnl_delta=DECIMAL_ZERO,
            event_at=now,
            metadata_json={"signal_id": str(signal.id), "mode": "demo"},
        )
        journal = TradeJournalEntry(
            position_id=position.id,
            symbol=position.symbol,
            entry_type=JournalEntryType.NOTE,
            title=f"Demo entry executed for {position.symbol}",
            body=note or "Execution foundation opened a demo position from a promoted signal.",
            entry_at=now,
            metadata_json={"signal_id": str(signal.id)},
        )
        system_event = SystemEvent(
            level=SystemEventLevel.INFO,
            source="execution_service",
            message=f"Demo execution opened position for {position.symbol}",
            idempotency_key=f"system-entry-{signal.id}",
            event_at=now,
            metadata_json={
                "signal_id": str(signal.id),
                "position_id": str(position.id),
                "order_id": str(order.id),
            },
        )
        db.add_all([fill, event, journal, system_event])

        signal.status = SignalStatus.ACCEPTED
        signal.metadata_json = {
            **(signal.metadata_json or {}),
            "last_execution_at": now.isoformat(),
            "position_id": str(position.id),
            "execution_mode": "demo",
        }
        db.flush()
        return ExecutionResult(
            signal=signal,
            risk_decision=decision,
            order=order,
            position=position,
            reused=False,
        )

    def close_position(
        self,
        db: Session,
        position_id: uuid.UUID,
        exit_price: Decimal,
        note: str | None = None,
    ) -> ExecutionResult:
        position = db.scalar(select(Position).where(Position.id == position_id))
        if position is None:
            raise PositionNotFoundError("position not found")
        if self._enum_string(position.status) != PositionStatus.OPEN.value:
            raise ExecutionConflictError("position_not_open")

        entry_signal_id = (
            position.metadata_json.get("signal_id") if position.metadata_json else None
        )
        signal = None
        if entry_signal_id is not None:
            signal = db.scalar(select(Signal).where(Signal.id == uuid.UUID(entry_signal_id)))

        now = datetime.now(UTC)
        realized_pnl = self._quantize(
            (exit_price - position.average_entry_price) * position.quantity
        )
        position.status = PositionStatus.CLOSED
        position.realized_pnl = realized_pnl
        position.unrealized_pnl = DECIMAL_ZERO
        position.closed_at = now
        position.metadata_json = {
            **(position.metadata_json or {}),
            "close_price": str(exit_price),
            "close_note": note,
        }
        db.flush()

        order = Order(
            signal_id=signal.id if signal is not None else None,
            position_id=position.id,
            client_order_id=f"demo-exit-{position.id}",
            exchange_order_id=f"demo-exit-{position.id}",
            symbol=position.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            price=exit_price,
            quantity=position.quantity,
            filled_quantity=position.quantity,
            fee=DECIMAL_ZERO,
            submitted_at=now,
            metadata_json={"mode": "demo", "note": note},
        )
        db.add(order)
        db.flush()

        fill = Fill(
            order_id=order.id,
            exchange_trade_id=f"demo-fill-exit-{order.id}",
            price=exit_price,
            quantity=position.quantity,
            fee=DECIMAL_ZERO,
            fee_asset="USDT",
            filled_at=now,
            metadata_json={"mode": "demo"},
        )
        event = PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.CLOSED,
            quantity_delta=-position.quantity,
            price=exit_price,
            realized_pnl_delta=realized_pnl,
            event_at=now,
            metadata_json={"mode": "demo"},
        )
        journal = TradeJournalEntry(
            position_id=position.id,
            symbol=position.symbol,
            entry_type=JournalEntryType.REVIEW,
            title=f"Demo position closed for {position.symbol}",
            body=note or "Execution foundation closed the demo position.",
            entry_at=now,
            metadata_json={"position_id": str(position.id)},
        )
        system_event = SystemEvent(
            level=SystemEventLevel.INFO,
            source="execution_service",
            message=f"Demo execution closed position for {position.symbol}",
            idempotency_key=f"system-exit-{position.id}",
            event_at=now,
            metadata_json={
                "position_id": str(position.id),
                "order_id": str(order.id),
                "realized_pnl": str(realized_pnl),
            },
        )
        db.add_all([fill, event, journal, system_event])
        db.flush()

        risk_decision = self._latest_risk_decision(db, signal.id if signal is not None else None)
        if risk_decision is None:
            risk_decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.APPROVED,
                reason_code="position_close_recorded",
                metadata_json={"position_id": str(position.id)},
            )
        return ExecutionResult(
            signal=signal or self._synthetic_signal(position),
            risk_decision=risk_decision,
            order=order,
            position=position,
            reused=False,
        )

    def _synthetic_signal(self, position: Position) -> Signal:
        signal = Signal(
            symbol=position.symbol,
            status=SignalStatus.ACCEPTED,
            side=position.side,
            entry_price=position.average_entry_price,
            stop_loss_price=None,
            take_profit_price=None,
            risk_amount=DECIMAL_ZERO,
            idempotency_key=f"synthetic-{position.id}",
            metadata_json={"position_id": str(position.id)},
        )
        signal.id = uuid.uuid4()
        signal.created_at = position.created_at
        return signal

    def _runtime_settings(self, db: Session) -> dict[str, Decimal | int | bool | str | list[str]]:
        raw = get_public_settings(db, self.settings)
        return {
            **raw,
            "demo_account_balance": Decimal(str(raw["demo_account_balance"])),
            "risk_per_trade": Decimal(str(raw["risk_per_trade"])),
            "daily_loss_limit": Decimal(str(raw["daily_loss_limit"])),
        }

    def _count_open_positions(self, db: Session) -> int:
        return len(
            list(
                db.scalars(select(Position).where(Position.status == PositionStatus.OPEN))
            )
        )

    def _realized_pnl_today(self, db: Session) -> Decimal:
        start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = list(
            db.scalars(
                select(Position).where(
                    Position.closed_at.is_not(None),
                    Position.closed_at >= start_of_day,
                )
            )
        )
        total = DECIMAL_ZERO
        for row in rows:
            total += row.realized_pnl
        return self._quantize(total)

    def _record_risk_decision(
        self,
        db: Session,
        signal: Signal | None,
        status: RiskDecisionStatus,
        reason_code: str,
        metadata_json: dict[str, str | list[str] | None],
    ) -> RiskDecision:
        runtime = self._runtime_settings(db)
        decision = RiskDecision(
            signal_id=signal.id if signal is not None else None,
            status=status,
            risk_per_trade=runtime["risk_per_trade"],
            daily_loss_limit=runtime["daily_loss_limit"],
            max_open_trades=int(runtime["maximum_open_trades"]),
            reason_code=reason_code,
            idempotency_key=(
                f"risk-{signal.id if signal is not None else uuid.uuid4()}-{uuid.uuid4()}"
            ),
            metadata_json=metadata_json,
        )
        db.add(decision)
        db.flush()
        return decision

    def _latest_risk_decision(
        self,
        db: Session,
        signal_id: uuid.UUID | None,
    ) -> RiskDecision | None:
        if signal_id is None:
            return None
        return db.scalar(
            select(RiskDecision)
            .where(RiskDecision.signal_id == signal_id)
            .order_by(RiskDecision.created_at.desc())
            .limit(1)
        )

    def _quantize(self, value: Decimal) -> Decimal:
        return value.quantize(DECIMAL_EIGHT_PLACES, rounding=ROUND_DOWN)

    def _enum_string(self, value: object) -> str:
        if isinstance(value, str):
            return value
        return str(value.value)
