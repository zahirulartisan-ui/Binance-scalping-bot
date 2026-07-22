from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.trades import ActiveTradesResponse, TelemetryFeedResponse, TradeJournalResponse
from app.services.trades_service import TradesService

router = APIRouter(prefix="/api/v1/trades", tags=["trades"])


@router.get("/active", response_model=ActiveTradesResponse)
def read_active_trades(
    db: Annotated[Session, Depends(get_db)],
) -> ActiveTradesResponse:
    return ActiveTradesResponse.model_validate(TradesService().list_active_trades(db))


@router.get("/journal", response_model=TradeJournalResponse)
def read_trade_journal(
    db: Annotated[Session, Depends(get_db)],
) -> TradeJournalResponse:
    return TradeJournalResponse.model_validate(TradesService().list_trade_journal(db))


@router.get("/telemetry", response_model=TelemetryFeedResponse)
def read_trade_telemetry(
    db: Annotated[Session, Depends(get_db)],
    event_limit: Annotated[int, Query(ge=1, le=100)] = 20,
    journal_limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> TelemetryFeedResponse:
    return TelemetryFeedResponse.model_validate(
        TradesService().telemetry_feed(db, event_limit=event_limit, journal_limit=journal_limit)
    )
