from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.schemas.regime import RegimeEvaluationResponse
from app.services.market_regime_service import (
    MarketRegimeService,
    RegimeEvaluation,
    RegimeUnavailableError,
)

router = APIRouter(prefix="/api/v1/regime", tags=["regime"])


def validate_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if not normalized.endswith("USDT") or not normalized.isalnum() or len(normalized) > 30:
        raise HTTPException(status_code=422, detail="invalid symbol")
    return normalized


def to_response(result: RegimeEvaluation) -> RegimeEvaluationResponse:
    return RegimeEvaluationResponse.model_validate(
        {
            "symbol": result.symbol,
            "evaluated_at": result.evaluated_at,
            "primary_regime": result.primary_regime.value,
            "entry_permission": result.entry_permission.value,
            "confidence_score": result.confidence_score,
            "trend_direction": result.trend_direction.value,
            "trend_strength_value": result.trend_strength_value,
            "volatility_value": result.volatility_value,
            "spread_value": result.spread_value,
            "data_fresh": result.data_fresh,
            "btc_regime": result.btc_regime.value,
            "market_wide_block": result.market_wide_block,
            "reasons": result.reasons,
            "safety_conditions": result.safety_conditions,
            "indicator_snapshot": result.indicator_snapshot,
        }
    )


@router.get("/market", response_model=RegimeEvaluationResponse)
def read_market_regime(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegimeEvaluationResponse:
    try:
        return to_response(MarketRegimeService(settings).evaluate_symbol(db, "BTCUSDT"))
    except RegimeUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{symbol}", response_model=RegimeEvaluationResponse)
def read_symbol_regime(
    symbol: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegimeEvaluationResponse:
    try:
        normalized = validate_symbol(symbol)
        return to_response(MarketRegimeService(settings).evaluate_symbol(db, normalized))
    except RegimeUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
