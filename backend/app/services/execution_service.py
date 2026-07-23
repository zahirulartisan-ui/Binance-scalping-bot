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
from app.models.market_data import ExchangeSymbol
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
from app.services.binance_client import BinanceClientError
from app.services.binance_trading_client import BinanceTradingClient
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
    unsupported_open_positions: int
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


@dataclass(frozen=True)
class PositionManagementResult:
    action: str
    position: Position
    order: Order | None
    events: list[PositionEvent]
    details: dict[str, str | int | list[str] | None]


@dataclass(frozen=True)
class MonitorSweepResult:
    checked_count: int
    actions: list[PositionManagementResult]


@dataclass(frozen=True)
class OrderSyncResult:
    checked_orders: int
    updated_orders: int
    new_fills: int
    closed_positions: int
    reasons: list[str]


class ExecutionService:
    def __init__(
        self,
        settings: Settings,
        trading_client: BinanceTradingClient | None = None,
    ) -> None:
        self.settings = settings
        self.trading_client = trading_client

    def get_status(self, db: Session) -> ExecutionStatusSnapshot:
        runtime = self._runtime_settings(db)
        open_positions = self._count_open_positions(db)
        expected_mode = "demo" if bool(runtime["demo_trading_mode"]) else "live"
        unsupported_open_positions = self._count_unsupported_open_positions(db, expected_mode)
        realized_pnl_today = self._realized_pnl_today(db)
        daily_loss_limit_amount = (
            runtime["demo_account_balance"] * runtime["daily_loss_limit"]
        ).quantize(DECIMAL_EIGHT_PLACES)
        reasons: list[str] = []
        if not runtime["execution_enabled"]:
            reasons.append("execution_disabled")
        if runtime["emergency_stop"]:
            reasons.append("emergency_stop_active")
        if not runtime["demo_trading_mode"] and (
            self.settings.binance_api_key is None or self.settings.binance_api_secret is None
        ):
            reasons.append("live_credentials_missing")
        if unsupported_open_positions > 0:
            reasons.append("unsupported_open_positions_present")
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
            unsupported_open_positions=unsupported_open_positions,
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

    def list_position_events(self, db: Session, position_id: uuid.UUID) -> list[PositionEvent]:
        return list(
            db.scalars(
                select(PositionEvent)
                .where(PositionEvent.position_id == position_id)
                .order_by(PositionEvent.event_at.asc(), PositionEvent.created_at.asc())
            )
        )

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

        if not bool(runtime["demo_trading_mode"]):
            return self._execute_live_signal(
                db=db,
                signal=signal,
                entry_price=entry_price,
                stop_loss=stop_loss,
                quantity=quantity,
                note=note,
                risk_budget=risk_budget,
            )

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
                "initial_stop_loss_price": str(stop_loss),
                "take_profit_price": str(signal.take_profit_price)
                if signal.take_profit_price is not None
                else None,
                "initial_quantity": str(quantity),
                "partial_take_profit_done": False,
                "break_even_moved": False,
                "trailing_stop_active": False,
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

    def _execute_live_signal(
        self,
        db: Session,
        signal: Signal,
        entry_price: Decimal,
        stop_loss: Decimal,
        quantity: Decimal,
        note: str | None,
        risk_budget: Decimal,
    ) -> ExecutionResult:
        symbol = db.scalar(select(ExchangeSymbol).where(ExchangeSymbol.symbol == signal.symbol))
        if symbol is None:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="exchange_symbol_not_ready",
                metadata_json={"symbol": signal.symbol},
            )
            raise ExecutionConflictError(decision.reason_code)

        order_quantity = self._quantize_step(quantity, symbol.step_size)
        order_price = self._quantize_step(entry_price, symbol.tick_size)
        order_notional = self._quantize(order_quantity * order_price)
        if order_quantity < symbol.minimum_quantity:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="order_quantity_below_minimum",
                metadata_json={
                    "symbol": signal.symbol,
                    "minimum_quantity": str(symbol.minimum_quantity),
                    "requested_quantity": str(order_quantity),
                },
            )
            raise ExecutionConflictError(decision.reason_code)
        if order_notional < symbol.minimum_notional:
            decision = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="order_notional_below_minimum",
                metadata_json={
                    "symbol": signal.symbol,
                    "minimum_notional": str(symbol.minimum_notional),
                    "requested_notional": str(order_notional),
                },
            )
            raise ExecutionConflictError(decision.reason_code)

        now = datetime.now(UTC)
        position = Position(
            symbol=signal.symbol,
            status=PositionStatus.OPEN,
            side=signal.side,
            quantity=DECIMAL_ZERO,
            average_entry_price=order_price,
            realized_pnl=DECIMAL_ZERO,
            unrealized_pnl=DECIMAL_ZERO,
            opened_at=now,
            metadata_json={
                "signal_id": str(signal.id),
                "mode": "live",
                "stop_loss_price": str(stop_loss),
                "initial_stop_loss_price": str(stop_loss),
                "take_profit_price": str(signal.take_profit_price)
                if signal.take_profit_price is not None
                else None,
                "initial_quantity": str(order_quantity),
                "requested_entry_price": str(order_price),
                "entry_order_pending": True,
                "note": note,
            },
        )
        db.add(position)
        db.flush()

        decision = self._record_risk_decision(
            db=db,
            signal=signal,
            status=RiskDecisionStatus.APPROVED,
            reason_code="execution_submitted",
            metadata_json={
                "mode": "live",
                "entry_price": str(order_price),
                "stop_loss_price": str(stop_loss),
                "quantity": str(order_quantity),
                "risk_budget": str(risk_budget),
            },
        )

        client_order_id = f"live-entry-{signal.id.hex[:20]}"
        try:
            response = self._get_trading_client().create_order(
                symbol=signal.symbol,
                side=OrderSide.BUY.value,
                order_type=OrderType.LIMIT.value,
                quantity=self._format_decimal(order_quantity),
                client_order_id=client_order_id,
                price=self._format_decimal(order_price),
                time_in_force="GTC",
            )
        except BinanceClientError as exc:
            position.status = PositionStatus.CLOSED
            position.closed_at = now
            position.metadata_json = {
                **(position.metadata_json or {}),
                "entry_order_pending": False,
                "submission_error": exc.__class__.__name__,
            }
            blocked = self._record_risk_decision(
                db=db,
                signal=signal,
                status=RiskDecisionStatus.BLOCKED,
                reason_code="live_order_submission_failed",
                metadata_json={"error_type": exc.__class__.__name__},
            )
            raise ExecutionConflictError(blocked.reason_code) from exc

        order = Order(
            signal_id=signal.id,
            position_id=position.id,
            client_order_id=str(response.get("clientOrderId") or client_order_id),
            exchange_order_id=str(response.get("orderId")) if response.get("orderId") else None,
            symbol=signal.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            status=self._map_binance_order_status(response.get("status")),
            price=order_price,
            quantity=order_quantity,
            filled_quantity=self._decimal_or_zero(response.get("executedQty")),
            fee=DECIMAL_ZERO,
            submitted_at=now,
            metadata_json={"mode": "live", "note": note, "raw_status": response.get("status")},
        )
        db.add(order)
        db.flush()

        new_fill_count = self._sync_order_fills_from_exchange_payload(
            db=db,
            order=order,
            payload_fills=response.get("fills"),
        )
        self._reconcile_live_position(db, position)

        signal.status = SignalStatus.ACCEPTED
        signal.metadata_json = {
            **(signal.metadata_json or {}),
            "last_execution_at": now.isoformat(),
            "position_id": str(position.id),
            "execution_mode": "live",
        }
        db.add(
            SystemEvent(
                level=SystemEventLevel.INFO,
                source="execution_service",
                message=f"Live execution submitted order for {position.symbol}",
                idempotency_key=f"system-live-entry-{signal.id}",
                event_at=now,
                metadata_json={
                    "signal_id": str(signal.id),
                    "position_id": str(position.id),
                    "order_id": str(order.id),
                    "new_fill_count": new_fill_count,
                },
            )
        )
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
        position = self._require_open_position(db, position_id)
        self._assert_demo_position(position)
        signal = self._signal_for_position(db, position)
        result = self._apply_exit(
            db=db,
            position=position,
            signal=signal,
            exit_price=exit_price,
            quantity=position.quantity,
            note=note,
            action="manual_close",
            event_type=PositionEventType.CLOSED,
            reason="manual_close",
        )
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
            order=result.order,
            position=result.position,
            reused=False,
        )

    def partial_close_position(
        self,
        db: Session,
        position_id: uuid.UUID,
        exit_price: Decimal,
        quantity: Decimal,
        note: str | None = None,
    ) -> PositionManagementResult:
        position = self._require_open_position(db, position_id)
        self._assert_demo_position(position)
        if quantity >= position.quantity:
            raise ExecutionConflictError("partial_close_quantity_must_be_less_than_position")
        signal = self._signal_for_position(db, position)
        return self._apply_exit(
            db=db,
            position=position,
            signal=signal,
            exit_price=exit_price,
            quantity=quantity,
            note=note,
            action="partial_close",
            event_type=PositionEventType.REDUCED,
            reason="manual_partial_close",
        )

    def move_stop(
        self,
        db: Session,
        position_id: uuid.UUID,
        new_stop_price: Decimal,
        note: str | None = None,
    ) -> PositionManagementResult:
        position = self._require_open_position(db, position_id)
        self._assert_demo_position(position)
        current_stop = self._stop_loss_price(position)
        if current_stop is not None and new_stop_price <= current_stop:
            raise ExecutionConflictError("new_stop_must_improve_existing_stop")

        position.metadata_json = {
            **(position.metadata_json or {}),
            "stop_loss_price": str(new_stop_price),
            "stop_update_note": note,
        }
        event = PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.STOP_UPDATED,
            quantity_delta=DECIMAL_ZERO,
            price=new_stop_price,
            realized_pnl_delta=DECIMAL_ZERO,
            event_at=datetime.now(UTC),
            metadata_json={"reason": "manual_stop_update", "note": note},
        )
        db.add(event)
        db.flush()
        return PositionManagementResult(
            action="move_stop",
            position=position,
            order=None,
            events=[event],
            details={"new_stop_price": str(new_stop_price), "note": note},
        )

    def run_monitor(
        self,
        db: Session,
        prices: dict[str, Decimal],
        note: str | None = None,
    ) -> MonitorSweepResult:
        rows = self.list_positions(db, status=PositionStatus.OPEN, limit=500)
        actions: list[PositionManagementResult] = []
        for position in rows:
            if not self._is_demo_position(position):
                continue
            price = prices.get(position.symbol)
            if price is None:
                continue
            actions.extend(self._monitor_position(db, position, price, note))
        db.flush()
        return MonitorSweepResult(checked_count=len(rows), actions=actions)

    def _monitor_position(
        self,
        db: Session,
        position: Position,
        current_price: Decimal,
        note: str | None,
    ) -> list[PositionManagementResult]:
        actions: list[PositionManagementResult] = []
        signal = self._signal_for_position(db, position)
        position.unrealized_pnl = self._quantize(
            (current_price - position.average_entry_price) * position.quantity
        )
        metadata = position.metadata_json or {}
        current_stop = self._stop_loss_price(position)
        take_profit = self._take_profit_price(position)
        if current_stop is not None and current_price <= current_stop:
            actions.append(
                self._apply_exit(
                    db=db,
                    position=position,
                    signal=signal,
                    exit_price=current_stop,
                    quantity=position.quantity,
                    note=note,
                    action="stop_loss_close",
                    event_type=PositionEventType.CLOSED,
                    reason="stop_loss_hit",
                )
            )
            return actions

        current_rr = self._reward_to_risk(position, current_price)
        partial_done = bool(metadata.get("partial_take_profit_done"))
        if (
            not partial_done
            and take_profit is not None
            and current_price >= take_profit
            and position.quantity > DECIMAL_ZERO
        ):
            partial_quantity = self._partial_take_profit_quantity(position)
            if partial_quantity > DECIMAL_ZERO and partial_quantity < position.quantity:
                actions.append(
                    self._apply_exit(
                        db=db,
                        position=position,
                        signal=signal,
                        exit_price=current_price,
                        quantity=partial_quantity,
                        note=note,
                        action="partial_take_profit",
                        event_type=PositionEventType.REDUCED,
                        reason="partial_take_profit_hit",
                    )
                )
                position.metadata_json = {
                    **(position.metadata_json or {}),
                    "partial_take_profit_done": True,
                }

        if self._enum_string(position.status) != PositionStatus.OPEN.value:
            return actions

        if (
            current_rr >= Decimal(str(self.settings.position_break_even_trigger_rr))
            and not bool((position.metadata_json or {}).get("break_even_moved"))
        ):
            event = self._update_stop(
                db=db,
                position=position,
                new_stop_price=position.average_entry_price,
                reason="auto_break_even",
                note=note,
            )
            position.metadata_json = {
                **(position.metadata_json or {}),
                "break_even_moved": True,
            }
            actions.append(
                PositionManagementResult(
                    action="move_stop_to_breakeven",
                    position=position,
                    order=None,
                    events=[event],
                    details={"reward_to_risk": str(current_rr)},
                )
            )

        if self._enum_string(position.status) != PositionStatus.OPEN.value:
            return actions

        trailing_trigger = Decimal(str(self.settings.position_trailing_stop_trigger_rr))
        trailing_buffer = Decimal(str(self.settings.position_trailing_stop_buffer_rr))
        if current_rr >= trailing_trigger:
            initial_risk = self._initial_risk_per_unit(position)
            candidate_stop = current_price - (initial_risk * trailing_buffer)
            current_stop = self._stop_loss_price(position)
            if current_stop is None or candidate_stop > current_stop:
                event = self._update_stop(
                    db=db,
                    position=position,
                    new_stop_price=self._quantize(candidate_stop),
                    reason="auto_trailing_stop",
                    note=note,
                )
                position.metadata_json = {
                    **(position.metadata_json or {}),
                    "trailing_stop_active": True,
                }
                actions.append(
                    PositionManagementResult(
                        action="trail_stop",
                        position=position,
                        order=None,
                        events=[event],
                        details={"reward_to_risk": str(current_rr)},
                    )
                )

        db.flush()
        return actions

    def _apply_exit(
        self,
        db: Session,
        position: Position,
        signal: Signal | None,
        exit_price: Decimal,
        quantity: Decimal,
        note: str | None,
        action: str,
        event_type: PositionEventType,
        reason: str,
    ) -> PositionManagementResult:
        if quantity <= DECIMAL_ZERO:
            raise ExecutionConflictError("exit_quantity_must_be_positive")
        quantity = self._quantize(quantity)
        if quantity > position.quantity:
            raise ExecutionConflictError("exit_quantity_exceeds_position")

        now = datetime.now(UTC)
        realized_pnl = self._quantize((exit_price - position.average_entry_price) * quantity)
        remaining_quantity = self._quantize(position.quantity - quantity)
        position.realized_pnl = self._quantize(position.realized_pnl + realized_pnl)
        position.quantity = remaining_quantity
        position.unrealized_pnl = DECIMAL_ZERO
        if remaining_quantity <= DECIMAL_ZERO:
            position.status = PositionStatus.CLOSED
            position.closed_at = now
            position.quantity = DECIMAL_ZERO
        position.metadata_json = {
            **(position.metadata_json or {}),
            "last_exit_reason": reason,
            "last_exit_price": str(exit_price),
            "last_exit_quantity": str(quantity),
            "last_exit_note": note,
        }
        db.flush()

        order = Order(
            signal_id=signal.id if signal is not None else None,
            position_id=position.id,
            client_order_id=f"demo-{action}-{position.id}-{uuid.uuid4().hex[:8]}",
            exchange_order_id=f"demo-{action}-{position.id}",
            symbol=position.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            price=exit_price,
            quantity=quantity,
            filled_quantity=quantity,
            fee=DECIMAL_ZERO,
            submitted_at=now,
            metadata_json={"mode": "demo", "note": note, "reason": reason},
        )
        db.add(order)
        db.flush()

        fill = Fill(
            order_id=order.id,
            exchange_trade_id=f"demo-fill-{action}-{order.id}",
            price=exit_price,
            quantity=quantity,
            fee=DECIMAL_ZERO,
            fee_asset="USDT",
            filled_at=now,
            metadata_json={"mode": "demo", "reason": reason},
        )
        event = PositionEvent(
            position_id=position.id,
            event_type=event_type,
            quantity_delta=-quantity,
            price=exit_price,
            realized_pnl_delta=realized_pnl,
            event_at=now,
            metadata_json={"reason": reason, "note": note},
        )
        journal = TradeJournalEntry(
            position_id=position.id,
            symbol=position.symbol,
            entry_type=JournalEntryType.REVIEW,
            title=f"Demo {action.replace('_', ' ')} for {position.symbol}",
            body=note or f"Execution management processed {action} for {position.symbol}.",
            entry_at=now,
            metadata_json={"position_id": str(position.id), "reason": reason},
        )
        system_event = SystemEvent(
            level=SystemEventLevel.INFO,
            source="execution_service",
            message=f"Demo {action} processed for {position.symbol}",
            idempotency_key=f"system-{action}-{position.id}-{uuid.uuid4()}",
            event_at=now,
            metadata_json={
                "position_id": str(position.id),
                "order_id": str(order.id),
                "reason": reason,
            },
        )
        db.add_all([fill, event, journal, system_event])
        db.flush()
        return PositionManagementResult(
            action=action,
            position=position,
            order=order,
            events=[event],
            details={"reason": reason, "note": note},
        )

    def _update_stop(
        self,
        db: Session,
        position: Position,
        new_stop_price: Decimal,
        reason: str,
        note: str | None,
    ) -> PositionEvent:
        current_stop = self._stop_loss_price(position)
        if current_stop is not None and new_stop_price <= current_stop:
            raise ExecutionConflictError("new_stop_must_improve_existing_stop")
        position.metadata_json = {
            **(position.metadata_json or {}),
            "stop_loss_price": str(new_stop_price),
            "last_stop_reason": reason,
        }
        event = PositionEvent(
            position_id=position.id,
            event_type=PositionEventType.STOP_UPDATED,
            quantity_delta=DECIMAL_ZERO,
            price=new_stop_price,
            realized_pnl_delta=DECIMAL_ZERO,
            event_at=datetime.now(UTC),
            metadata_json={"reason": reason, "note": note},
        )
        db.add(event)
        db.flush()
        return event

    def _signal_for_position(self, db: Session, position: Position) -> Signal | None:
        entry_signal_id = (position.metadata_json or {}).get("signal_id")
        if entry_signal_id is None:
            return None
        try:
            parsed_signal_id = uuid.UUID(str(entry_signal_id))
        except (TypeError, ValueError):
            return None
        return db.scalar(select(Signal).where(Signal.id == parsed_signal_id))

    def _require_open_position(self, db: Session, position_id: uuid.UUID) -> Position:
        position = db.scalar(select(Position).where(Position.id == position_id))
        if position is None:
            raise PositionNotFoundError("position not found")
        if self._enum_string(position.status) != PositionStatus.OPEN.value:
            raise ExecutionConflictError("position_not_open")
        return position

    def _partial_take_profit_quantity(self, position: Position) -> Decimal:
        initial_quantity = Decimal(
            str((position.metadata_json or {}).get("initial_quantity") or position.quantity)
        )
        partial = self._quantize(
            initial_quantity * Decimal(str(self.settings.position_partial_take_profit_fraction))
        )
        return min(partial, position.quantity)

    def _reward_to_risk(self, position: Position, current_price: Decimal) -> Decimal:
        initial_risk = self._initial_risk_per_unit(position)
        if initial_risk <= DECIMAL_ZERO:
            return DECIMAL_ZERO
        reward = current_price - position.average_entry_price
        return self._quantize(reward / initial_risk)

    def _initial_risk_per_unit(self, position: Position) -> Decimal:
        metadata = position.metadata_json or {}
        initial_stop = Decimal(
            str(metadata.get("initial_stop_loss_price") or metadata.get("stop_loss_price") or "0")
        )
        return self._quantize(position.average_entry_price - initial_stop)

    def _stop_loss_price(self, position: Position) -> Decimal | None:
        value = (position.metadata_json or {}).get("stop_loss_price")
        if value is None:
            return None
        return Decimal(str(value))

    def _take_profit_price(self, position: Position) -> Decimal | None:
        value = (position.metadata_json or {}).get("take_profit_price")
        if value is None:
            return None
        return Decimal(str(value))

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

    def sync_live_orders(self, db: Session, limit: int = 100) -> OrderSyncResult:
        live_orders = [
            row
            for row in db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit))
            if self._is_live_order(row)
            and self._enum_string(row.status)
            in {
                OrderStatus.CREATED.value,
                OrderStatus.SUBMITTED.value,
                OrderStatus.ACKNOWLEDGED.value,
                OrderStatus.PARTIALLY_FILLED.value,
            }
        ]
        if not live_orders:
            return OrderSyncResult(
                checked_orders=0,
                updated_orders=0,
                new_fills=0,
                closed_positions=0,
                reasons=[],
            )

        client = self._get_trading_client()
        updated_orders = 0
        new_fills = 0
        closed_positions = 0
        reasons: list[str] = []

        for order in live_orders:
            try:
                payload = client.get_order(
                    symbol=order.symbol,
                    order_id=order.exchange_order_id,
                    client_order_id=order.client_order_id,
                )
                updated = self._apply_exchange_order_snapshot(order, payload)
                trades = client.get_my_trades(
                    symbol=order.symbol,
                    order_id=order.exchange_order_id,
                )
                new_fills += self._sync_order_fills_from_exchange_trades(db, order, trades)
                if updated:
                    updated_orders += 1
                position = (
                    db.scalar(select(Position).where(Position.id == order.position_id))
                    if order.position_id is not None
                    else None
                )
                if position is not None:
                    was_closed = self._enum_string(position.status) == PositionStatus.CLOSED.value
                    self._reconcile_live_position(db, position)
                    is_closed = self._enum_string(position.status) == PositionStatus.CLOSED.value
                    if not was_closed and is_closed:
                        closed_positions += 1
            except BinanceClientError as exc:
                reasons.append(f"{order.symbol}:{exc.__class__.__name__}")

        if updated_orders > 0 or new_fills > 0 or closed_positions > 0 or reasons:
            db.add(
                SystemEvent(
                    level=SystemEventLevel.WARNING if reasons else SystemEventLevel.INFO,
                    source="order_sync_service",
                    message=(
                        f"Live order sync checked {len(live_orders)} orders, updated "
                        f"{updated_orders}, and imported {new_fills} fills."
                    ),
                    idempotency_key=f"live-order-sync-{uuid.uuid4()}",
                    event_at=datetime.now(UTC),
                    metadata_json={
                        "checked_orders": len(live_orders),
                        "updated_orders": updated_orders,
                        "new_fills": new_fills,
                        "closed_positions": closed_positions,
                        "reasons": reasons,
                    },
                )
            )

        return OrderSyncResult(
            checked_orders=len(live_orders),
            updated_orders=updated_orders,
            new_fills=new_fills,
            closed_positions=closed_positions,
            reasons=reasons,
        )

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
            list(db.scalars(select(Position).where(Position.status == PositionStatus.OPEN)))
        )

    def _count_unsupported_open_positions(self, db: Session, expected_mode: str) -> int:
        return sum(
            1
            for row in db.scalars(select(Position).where(Position.status == PositionStatus.OPEN))
            if self._position_mode(row) != expected_mode
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

    def _quantize_step(self, value: Decimal, step: Decimal) -> Decimal:
        if step <= DECIMAL_ZERO:
            return self._quantize(value)
        units = (value / step).to_integral_value(rounding=ROUND_DOWN)
        return self._quantize(units * step)

    def _format_decimal(self, value: Decimal) -> str:
        return format(value.normalize(), "f")

    def _decimal_or_zero(self, value: object) -> Decimal:
        if value in {None, ""}:
            return DECIMAL_ZERO
        return self._quantize(Decimal(str(value)))

    def _map_binance_order_status(self, status: object) -> OrderStatus:
        mapping = {
            "NEW": OrderStatus.ACKNOWLEDGED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.FAILED,
            "PENDING_CANCEL": OrderStatus.SUBMITTED,
        }
        return mapping.get(str(status or "").upper(), OrderStatus.SUBMITTED)

    def _apply_exchange_order_snapshot(self, order: Order, payload: dict[str, object]) -> bool:
        changed = False
        exchange_order_id = payload.get("orderId")
        mapped_status = self._map_binance_order_status(payload.get("status"))
        executed_quantity = self._decimal_or_zero(payload.get("executedQty"))
        if exchange_order_id is not None and str(exchange_order_id) != order.exchange_order_id:
            order.exchange_order_id = str(exchange_order_id)
            changed = True
        if order.status != mapped_status:
            order.status = mapped_status
            changed = True
        if order.filled_quantity != executed_quantity:
            order.filled_quantity = executed_quantity
            changed = True
        payload_price = payload.get("price")
        if payload_price not in {None, "", "0.00000000"}:
            parsed_price = self._quantize(Decimal(str(payload_price)))
            if order.price != parsed_price:
                order.price = parsed_price
                changed = True
        order.metadata_json = {
            **(order.metadata_json or {}),
            "raw_status": payload.get("status"),
            "update_time": payload.get("updateTime"),
        }
        return changed

    def _sync_order_fills_from_exchange_payload(
        self,
        db: Session,
        order: Order,
        payload_fills: object,
    ) -> int:
        if not isinstance(payload_fills, list):
            return 0
        trade_rows = []
        for index, row in enumerate(payload_fills, start=1):
            if not isinstance(row, dict):
                continue
            trade_rows.append(
                {
                    "id": row.get("tradeId") or f"{order.client_order_id}-{index}",
                    "price": row.get("price"),
                    "qty": row.get("qty"),
                    "commission": row.get("commission", "0"),
                    "commissionAsset": row.get("commissionAsset", "USDT"),
                    "time": int(datetime.now(UTC).timestamp() * 1000),
                }
            )
        return self._sync_order_fills_from_exchange_trades(db, order, trade_rows)

    def _sync_order_fills_from_exchange_trades(
        self,
        db: Session,
        order: Order,
        trades: list[dict[str, object]],
    ) -> int:
        imported = 0
        for trade in trades:
            exchange_trade_id = str(trade.get("id"))
            existing = db.scalar(select(Fill).where(Fill.exchange_trade_id == exchange_trade_id))
            if existing is not None:
                continue
            quantity = self._decimal_or_zero(trade.get("qty"))
            price = self._decimal_or_zero(trade.get("price"))
            fee = self._decimal_or_zero(trade.get("commission"))
            filled_at_ms = int(trade.get("time") or int(datetime.now(UTC).timestamp() * 1000))
            filled_at = datetime.fromtimestamp(filled_at_ms / 1000, tz=UTC)
            fill = Fill(
                order_id=order.id,
                exchange_trade_id=exchange_trade_id,
                price=price,
                quantity=quantity,
                fee=fee,
                fee_asset=str(trade.get("commissionAsset") or "USDT"),
                filled_at=filled_at,
                metadata_json={"mode": "live"},
            )
            db.add(fill)
            order.filled_quantity = self._quantize(order.filled_quantity + quantity)
            order.fee = self._quantize(order.fee + fee)
            position = (
                db.scalar(select(Position).where(Position.id == order.position_id))
                if order.position_id is not None
                else None
            )
            if position is not None:
                event_type = (
                    PositionEventType.OPENED
                    if self._enum_string(order.side) == OrderSide.BUY.value
                    else PositionEventType.REDUCED
                )
                quantity_delta = quantity if event_type == PositionEventType.OPENED else -quantity
                db.add(
                    PositionEvent(
                        position_id=position.id,
                        event_type=event_type,
                        quantity_delta=quantity_delta,
                        price=price,
                        realized_pnl_delta=DECIMAL_ZERO,
                        event_at=filled_at,
                        metadata_json={
                            "reason": "live_order_sync",
                            "exchange_trade_id": exchange_trade_id,
                            "order_id": str(order.id),
                        },
                    )
                )
            imported += 1
        if imported > 0:
            db.flush()
        return imported

    def _reconcile_live_position(self, db: Session, position: Position) -> None:
        orders = list(
            db.scalars(
                select(Order)
                .where(Order.position_id == position.id)
                .order_by(Order.created_at.asc())
            )
        )
        fills = list(
            db.scalars(
                select(Fill)
                .join(Order, Fill.order_id == Order.id)
                .where(Order.position_id == position.id)
                .order_by(Fill.filled_at.asc(), Fill.created_at.asc())
            )
        )
        buy_fills = [
            fill
            for fill in fills
            if self._enum_string(fill.order.side) == OrderSide.BUY.value
        ]
        sell_fills = [
            fill
            for fill in fills
            if self._enum_string(fill.order.side) == OrderSide.SELL.value
        ]
        total_buy_quantity = sum((fill.quantity for fill in buy_fills), DECIMAL_ZERO)
        total_sell_quantity = sum((fill.quantity for fill in sell_fills), DECIMAL_ZERO)
        if total_buy_quantity > DECIMAL_ZERO:
            total_buy_notional = sum(
                (fill.price * fill.quantity for fill in buy_fills), DECIMAL_ZERO
            )
            position.average_entry_price = self._quantize(total_buy_notional / total_buy_quantity)
        net_quantity = self._quantize(total_buy_quantity - total_sell_quantity)
        position.quantity = max(net_quantity, DECIMAL_ZERO)
        realized_pnl = sum(
            ((fill.price - position.average_entry_price) * fill.quantity for fill in sell_fills),
            DECIMAL_ZERO,
        )
        position.realized_pnl = self._quantize(realized_pnl)
        position.unrealized_pnl = DECIMAL_ZERO
        position.metadata_json = {
            **(position.metadata_json or {}),
            "entry_order_pending": total_buy_quantity <= DECIMAL_ZERO,
            "last_sync_at": datetime.now(UTC).isoformat(),
        }
        if position.quantity <= DECIMAL_ZERO:
            if total_buy_quantity <= DECIMAL_ZERO and all(
                self._enum_string(order.status)
                in {
                    OrderStatus.CANCELED.value,
                    OrderStatus.REJECTED.value,
                    OrderStatus.FAILED.value,
                }
                for order in orders
            ):
                position.status = PositionStatus.CLOSED
                position.closed_at = position.closed_at or datetime.now(UTC)
                position.metadata_json = {
                    **(position.metadata_json or {}),
                    "last_exit_reason": "entry_unfilled",
                }
            elif total_sell_quantity > DECIMAL_ZERO:
                position.status = PositionStatus.CLOSED
                position.closed_at = max(
                    (fill.filled_at for fill in sell_fills), default=datetime.now(UTC)
                )
            else:
                position.status = PositionStatus.OPEN
        else:
            position.status = PositionStatus.OPEN
            position.closed_at = None

    def _get_trading_client(self) -> BinanceTradingClient:
        if self.trading_client is not None:
            return self.trading_client
        if self.settings.binance_api_key is None or self.settings.binance_api_secret is None:
            raise ExecutionConflictError("live_credentials_missing")
        self.trading_client = BinanceTradingClient(
            api_key=self.settings.binance_api_key.get_secret_value(),
            api_secret=self.settings.binance_api_secret.get_secret_value(),
            base_url=self.settings.binance_trading_base_url,
            timeout_seconds=self.settings.binance_trading_timeout_seconds,
            max_retries=self.settings.binance_trading_max_retries,
            backoff_seconds=self.settings.binance_trading_backoff_seconds,
        )
        return self.trading_client

    def _is_demo_position(self, position: Position) -> bool:
        return self._position_mode(position) == "demo"

    def _position_mode(self, position: Position) -> str:
        metadata = position.metadata_json or {}
        mode = metadata.get("mode") or metadata.get("execution_mode") or "demo"
        return str(mode).lower()

    def _is_live_order(self, order: Order) -> bool:
        metadata = order.metadata_json or {}
        return str(metadata.get("mode") or "").lower() == "live"

    def _assert_demo_position(self, position: Position) -> None:
        if not self._is_demo_position(position):
            raise ExecutionConflictError("position_mode_not_supported")

    def _enum_string(self, value: object) -> str:
        if isinstance(value, str):
            return value
        return str(value.value)
