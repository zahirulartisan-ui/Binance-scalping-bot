from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.models.enums import CandleTimeframe
from app.models.market_data import ExchangeSymbol, MarketDataCycle, MarketSnapshot, OhlcvCandle
from app.schemas.market_data import (
    CandleResponse,
    MarketDataStatusResponse,
    SnapshotResponse,
    SymbolResponse,
)

router = APIRouter(prefix="/api/v1/market-data", tags=["market-data"])


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if not normalized.endswith("USDT") or not normalized.isalnum() or len(normalized) > 30:
        raise HTTPException(status_code=422, detail="invalid symbol")
    return normalized


@router.get("/status", response_model=MarketDataStatusResponse)
def market_data_status(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketDataStatusResponse:
    latest = db.scalars(
        select(MarketDataCycle).order_by(MarketDataCycle.started_at.desc()).limit(1)
    ).first()
    runner = getattr(request.app.state, "market_data_runner", None)
    return MarketDataStatusResponse(
        collection_enabled=settings.market_data_collection_enabled,
        runner_active=bool(runner and runner.is_running),
        latest_cycle_status=latest.status if latest else None,
        latest_cycle_started_at=latest.started_at if latest else None,
        latest_cycle_finished_at=latest.finished_at if latest else None,
        latest_cycle_rejections=latest.rejection_reasons if latest else {},
    )


@router.get("/symbols", response_model=list[SymbolResponse])
def read_symbols(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    active_only: bool = True,
) -> list[SymbolResponse]:
    statement = select(ExchangeSymbol).order_by(ExchangeSymbol.symbol).limit(limit)
    if active_only:
        statement = statement.where(ExchangeSymbol.trading_status == "TRADING")
    return [
        SymbolResponse.model_validate(row, from_attributes=True) for row in db.scalars(statement)
    ]


@router.get("/candles", response_model=list[CandleResponse])
def read_candles(
    db: Annotated[Session, Depends(get_db)],
    symbol: str,
    timeframe: CandleTimeframe,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[CandleResponse]:
    normalized = normalize_symbol(symbol)
    if start_time and end_time and start_time >= end_time:
        raise HTTPException(status_code=422, detail="start_time must be before end_time")
    statement = (
        select(OhlcvCandle)
        .where(OhlcvCandle.symbol == normalized, OhlcvCandle.timeframe == timeframe)
        .order_by(OhlcvCandle.open_time.desc())
        .limit(limit)
    )
    if start_time:
        statement = statement.where(OhlcvCandle.open_time >= start_time)
    if end_time:
        statement = statement.where(OhlcvCandle.open_time < end_time)
    return [
        CandleResponse.model_validate(row, from_attributes=True) for row in db.scalars(statement)
    ]


@router.get("/snapshot", response_model=SnapshotResponse | None)
def read_snapshot(
    db: Annotated[Session, Depends(get_db)],
    symbol: str,
) -> SnapshotResponse | None:
    normalized = normalize_symbol(symbol)
    row = db.scalars(
        select(MarketSnapshot)
        .where(MarketSnapshot.symbol == normalized)
        .order_by(MarketSnapshot.snapshot_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return SnapshotResponse.model_validate(row, from_attributes=True)
