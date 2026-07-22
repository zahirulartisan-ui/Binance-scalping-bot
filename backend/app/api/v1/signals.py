from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.models.enums import SignalStatus
from app.models.trading import Signal
from app.schemas.signals import SignalPromotionResponse, SignalResponse
from app.services.signals_service import SignalsService

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


def _enum_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError("signal enum value must be str or StrEnum")


def _signal_response(row: Signal) -> SignalResponse:
    metadata = row.metadata_json or {}
    return SignalResponse(
        signal_id=str(row.id),
        scanner_decision_id=str(row.scanner_decision_id) if row.scanner_decision_id else None,
        symbol=row.symbol,
        status=_enum_value(row.status),
        side=_enum_value(row.side),
        entry_price=row.entry_price,
        stop_loss_price=row.stop_loss_price,
        take_profit_price=row.take_profit_price,
        risk_amount=row.risk_amount,
        expires_at=row.expires_at,
        created_at=row.created_at,
        signal_grade=metadata.get("signal_grade"),
        signal_score=metadata.get("signal_score"),
        setup_id=metadata.get("setup_id"),
        setup_state=metadata.get("setup_state"),
        strategy_name=metadata.get("strategy_name"),
        strategy_version=metadata.get("strategy_version"),
        reason_code=metadata.get("reason_code"),
        reasons=list(metadata.get("reasons", [])),
        metadata_json=metadata,
    )


@router.post("/promote-latest", response_model=SignalPromotionResponse)
def promote_latest_signals(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    refresh_scanner: bool = False,
) -> SignalPromotionResponse:
    result = SignalsService(settings).promote_latest(db, limit, refresh_scanner)
    return SignalPromotionResponse(
        promoted_count=result.promoted_count,
        reused_count=result.reused_count,
        signals=[_signal_response(item) for item in result.signals],
    )


@router.get("", response_model=list[SignalResponse])
def read_signals(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    status: SignalStatus | None = None,
    symbol: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SignalResponse]:
    normalized = symbol.upper() if symbol else None
    rows = SignalsService(settings).list_signals(db, status, normalized, limit)
    return [_signal_response(item) for item in rows]


@router.get("/{signal_id}", response_model=SignalResponse)
def read_signal(
    signal_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SignalResponse:
    try:
        parsed = uuid.UUID(signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid signal id") from exc
    row = SignalsService(settings).get_signal(db, parsed)
    if row is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return _signal_response(row)
