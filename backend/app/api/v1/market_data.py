from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from app.services.market_data_service import TIMEFRAME_SECONDS

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

    db_candles = list(db.scalars(statement))
    candles_res = [
        CandleResponse.model_validate(row, from_attributes=True) for row in db_candles
    ]

    def ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    # Dynamic synchronization between orderbook last price and latest closed candle
    now = datetime.now(UTC)
    if not end_time or end_time >= now:
        snapshot = db.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == normalized)
            .order_by(MarketSnapshot.snapshot_at.desc())
            .limit(1)
        ).first()

        if snapshot:
            last_price = float(snapshot.last_price)
            interval_seconds = TIMEFRAME_SECONDS[timeframe]
            now_ts = now.timestamp()
            current_open_ts = int(now_ts // interval_seconds) * interval_seconds
            current_open_time = ensure_utc(datetime.fromtimestamp(current_open_ts, UTC))
            current_close_time = (
                current_open_time
                + timedelta(seconds=interval_seconds)
                - timedelta(milliseconds=1)
            )

            if candles_res:
                # Find if they are in descending order or ascending order
                is_desc = True
                if len(candles_res) > 1:
                    is_desc = ensure_utc(candles_res[0].open_time) > ensure_utc(
                        candles_res[-1].open_time
                    )

                if is_desc:
                    latest_closed = candles_res[0]
                    latest_open_utc = ensure_utc(latest_closed.open_time)
                    if latest_open_utc == current_open_time:
                        latest_closed.close_price = last_price
                        if last_price > latest_closed.high_price:
                            latest_closed.high_price = last_price
                        if last_price < latest_closed.low_price:
                            latest_closed.low_price = last_price
                    elif latest_open_utc < current_open_time:
                        live_candle = CandleResponse(
                            symbol=normalized,
                            timeframe=timeframe,
                            open_time=current_open_time,
                            close_time=current_close_time,
                            open_price=latest_closed.close_price,
                            high_price=max(latest_closed.close_price, last_price),
                            low_price=min(latest_closed.close_price, last_price),
                            close_price=last_price,
                            volume=0.0,
                            quote_volume=0.0,
                            trade_count=0,
                        )
                        candles_res.insert(0, live_candle)
                        if len(candles_res) > limit:
                            candles_res.pop()
                else:
                    latest_closed = candles_res[-1]
                    latest_open_utc = ensure_utc(latest_closed.open_time)
                    if latest_open_utc == current_open_time:
                        latest_closed.close_price = last_price
                        if last_price > latest_closed.high_price:
                            latest_closed.high_price = last_price
                        if last_price < latest_closed.low_price:
                            latest_closed.low_price = last_price
                    elif latest_open_utc < current_open_time:
                        live_candle = CandleResponse(
                            symbol=normalized,
                            timeframe=timeframe,
                            open_time=current_open_time,
                            close_time=current_close_time,
                            open_price=latest_closed.close_price,
                            high_price=max(latest_closed.close_price, last_price),
                            low_price=min(latest_closed.close_price, last_price),
                            close_price=last_price,
                            volume=0.0,
                            quote_volume=0.0,
                            trade_count=0,
                        )
                        candles_res.append(live_candle)
                        if len(candles_res) > limit:
                            candles_res.pop(0)
            else:
                live_candle = CandleResponse(
                    symbol=normalized,
                    timeframe=timeframe,
                    open_time=current_open_time,
                    close_time=current_close_time,
                    open_price=last_price,
                    high_price=last_price,
                    low_price=last_price,
                    close_price=last_price,
                    volume=0.0,
                    quote_volume=0.0,
                    trade_count=0,
                )
                candles_res.append(live_candle)

    return candles_res


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
