from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.models.enums import PositionStatus
from app.models.trading import Order, Position, PositionEvent, RiskDecision, Signal
from app.schemas.execution import (
    ClosePositionRequest,
    ExecuteSignalRequest,
    ExecutionStatusResponse,
    MonitorRunRequest,
    MonitorSweepResponse,
    MoveStopRequest,
    OrderResponse,
    PartialClosePositionRequest,
    PositionEventResponse,
    PositionManagementResponse,
    PositionResponse,
    RiskDecisionResponse,
    SignalExecutionResponse,
)
from app.services.execution_service import (
    ExecutionConflictError,
    ExecutionService,
    PositionNotFoundError,
    SignalExecutionNotFoundError,
)

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


def _enum_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError("execution enum value must be str or StrEnum")


def _risk_decision_response(row: RiskDecision) -> RiskDecisionResponse:
    return RiskDecisionResponse(
        risk_decision_id=str(row.id),
        status=_enum_value(row.status),
        reason_code=row.reason_code,
        risk_per_trade=row.risk_per_trade,
        daily_loss_limit=row.daily_loss_limit,
        max_open_trades=row.max_open_trades,
        created_at=row.created_at,
        metadata_json=row.metadata_json or {},
    )


def _order_response(row: Order) -> OrderResponse:
    return OrderResponse(
        order_id=str(row.id),
        signal_id=str(row.signal_id) if row.signal_id else None,
        position_id=str(row.position_id) if row.position_id else None,
        client_order_id=row.client_order_id,
        exchange_order_id=row.exchange_order_id,
        symbol=row.symbol,
        side=_enum_value(row.side),
        order_type=_enum_value(row.order_type),
        status=_enum_value(row.status),
        price=row.price,
        quantity=row.quantity,
        filled_quantity=row.filled_quantity,
        fee=row.fee,
        submitted_at=row.submitted_at,
        created_at=row.created_at,
        metadata_json=row.metadata_json or {},
    )


def _position_response(row: Position) -> PositionResponse:
    metadata = row.metadata_json or {}
    return PositionResponse(
        position_id=str(row.id),
        symbol=row.symbol,
        status=_enum_value(row.status),
        side=_enum_value(row.side),
        quantity=row.quantity,
        average_entry_price=row.average_entry_price,
        realized_pnl=row.realized_pnl,
        unrealized_pnl=row.unrealized_pnl,
        opened_at=row.opened_at,
        closed_at=row.closed_at,
        signal_id=metadata.get("signal_id"),
        created_at=row.created_at,
        metadata_json=metadata,
    )


def _position_event_response(row: PositionEvent) -> PositionEventResponse:
    return PositionEventResponse(
        event_id=str(row.id),
        position_id=str(row.position_id),
        event_type=_enum_value(row.event_type),
        quantity_delta=row.quantity_delta,
        price=row.price,
        realized_pnl_delta=row.realized_pnl_delta,
        event_at=row.event_at,
        created_at=row.created_at,
        metadata_json=row.metadata_json or {},
    )


def _position_management_response(result: object) -> PositionManagementResponse:
    return PositionManagementResponse(
        action=result.action,
        position=_position_response(result.position),
        order=_order_response(result.order) if result.order is not None else None,
        events=[_position_event_response(item) for item in result.events],
        details=result.details,
    )


def _execution_response(
    signal: Signal,
    decision: RiskDecision,
    order: Order,
    position: Position,
    reused: bool,
) -> SignalExecutionResponse:
    return SignalExecutionResponse(
        signal_id=str(signal.id),
        reused=reused,
        mode="demo",
        risk_decision=_risk_decision_response(decision),
        order=_order_response(order),
        position=_position_response(position),
    )


@router.get("/status", response_model=ExecutionStatusResponse)
def read_execution_status(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExecutionStatusResponse:
    snapshot = ExecutionService(settings).get_status(db)
    return ExecutionStatusResponse(
        execution_enabled=snapshot.execution_enabled,
        demo_trading_mode=snapshot.demo_trading_mode,
        emergency_stop=snapshot.emergency_stop,
        demo_account_balance=snapshot.demo_account_balance,
        risk_per_trade=snapshot.risk_per_trade,
        daily_loss_limit=snapshot.daily_loss_limit,
        daily_loss_limit_amount=snapshot.daily_loss_limit_amount,
        maximum_open_trades=snapshot.maximum_open_trades,
        open_positions=snapshot.open_positions,
        realized_pnl_today=snapshot.realized_pnl_today,
        executable=snapshot.executable,
        reasons=snapshot.reasons,
    )


@router.post("/signals/{signal_id}/execute", response_model=SignalExecutionResponse)
def execute_signal(
    signal_id: str,
    payload: ExecuteSignalRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SignalExecutionResponse:
    try:
        parsed = uuid.UUID(signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid signal id") from exc

    try:
        result = ExecutionService(settings).execute_signal(
            db,
            parsed,
            quantity_override=payload.quantity_override,
            entry_price_override=payload.entry_price_override,
            note=payload.note,
        )
    except SignalExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _execution_response(
        result.signal,
        result.risk_decision,
        result.order,
        result.position,
        result.reused,
    )


@router.get("/positions", response_model=list[PositionResponse])
def read_positions(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    status: PositionStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[PositionResponse]:
    rows = ExecutionService(settings).list_positions(db, status=status, limit=limit)
    return [_position_response(item) for item in rows]


@router.get("/positions/{position_id}", response_model=PositionResponse)
def read_position(
    position_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PositionResponse:
    try:
        parsed = uuid.UUID(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid position id") from exc

    row = ExecutionService(settings).get_position(db, parsed)
    if row is None:
        raise HTTPException(status_code=404, detail="position not found")
    return _position_response(row)


@router.get("/positions/{position_id}/events", response_model=list[PositionEventResponse])
def read_position_events(
    position_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[PositionEventResponse]:
    try:
        parsed = uuid.UUID(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid position id") from exc

    service = ExecutionService(settings)
    row = service.get_position(db, parsed)
    if row is None:
        raise HTTPException(status_code=404, detail="position not found")
    return [_position_event_response(item) for item in service.list_position_events(db, parsed)]


@router.post("/positions/{position_id}/close", response_model=SignalExecutionResponse)
def close_position(
    position_id: str,
    payload: ClosePositionRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SignalExecutionResponse:
    try:
        parsed = uuid.UUID(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid position id") from exc

    try:
        result = ExecutionService(settings).close_position(
            db,
            parsed,
            exit_price=payload.exit_price,
            note=payload.note,
        )
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _execution_response(
        result.signal,
        result.risk_decision,
        result.order,
        result.position,
        result.reused,
    )


@router.post(
    "/positions/{position_id}/partial-close",
    response_model=PositionManagementResponse,
)
def partial_close_position(
    position_id: str,
    payload: PartialClosePositionRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PositionManagementResponse:
    try:
        parsed = uuid.UUID(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid position id") from exc

    try:
        result = ExecutionService(settings).partial_close_position(
            db,
            parsed,
            exit_price=payload.exit_price,
            quantity=payload.quantity,
            note=payload.note,
        )
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _position_management_response(result)


@router.post("/positions/{position_id}/move-stop", response_model=PositionManagementResponse)
def move_stop(
    position_id: str,
    payload: MoveStopRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PositionManagementResponse:
    try:
        parsed = uuid.UUID(position_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid position id") from exc

    try:
        result = ExecutionService(settings).move_stop(
            db,
            parsed,
            new_stop_price=payload.new_stop_price,
            note=payload.note,
        )
    except PositionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _position_management_response(result)


@router.post("/monitor/run", response_model=MonitorSweepResponse)
def run_monitor(
    payload: MonitorRunRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MonitorSweepResponse:
    prices = {item.symbol.upper(): item.price for item in payload.prices}
    result = ExecutionService(settings).run_monitor(db, prices=prices, note=payload.note)
    return MonitorSweepResponse(
        checked_count=result.checked_count,
        action_count=len(result.actions),
        actions=[_position_management_response(item) for item in result.actions],
    )
