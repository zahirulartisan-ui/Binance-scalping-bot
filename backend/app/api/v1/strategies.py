from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.database.session import get_db
from app.models.enums import StrategySetupState
from app.schemas.strategy import (
    StrategyEvaluationResponse,
    StrategyInfoResponse,
    StrategySetupResponse,
)
from app.services.trend_pullback_strategy import (
    StrategyEvaluation,
    StrategyEvaluationError,
    StrategySetupRepository,
    TrendPullbackStrategyService,
    evaluation_to_dict,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


def validate_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if not normalized.endswith("USDT") or not normalized.isalnum() or len(normalized) > 30:
        raise HTTPException(status_code=422, detail="invalid symbol")
    return normalized


def to_response(result: StrategyEvaluation) -> StrategyEvaluationResponse:
    payload = evaluation_to_dict(result)
    payload["direction"] = result.direction.value
    payload["setup_state"] = result.setup_state.value
    payload["regime"] = result.regime.value
    payload["regime_permission"] = result.regime_permission.value
    payload["btc_regime"] = result.btc_regime.value
    return StrategyEvaluationResponse.model_validate(payload)


@router.get("", response_model=list[StrategyInfoResponse])
def read_strategies(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[StrategyInfoResponse]:
    service = TrendPullbackStrategyService(settings)
    return [StrategyInfoResponse.model_validate(item) for item in service.list_strategies()]


@router.get("/trend-pullback/{symbol}", response_model=StrategyEvaluationResponse)
def read_trend_pullback_strategy(
    symbol: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh: bool = False,
) -> StrategyEvaluationResponse:
    try:
        normalized = validate_symbol(symbol)
        result = TrendPullbackStrategyService(settings).evaluate_symbol(db, normalized, refresh)
        return to_response(result)
    except StrategyEvaluationError as exc:
        detail = str(exc)
        status_code = 409 if "scanner rejection" in detail or "regime" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/setups", response_model=list[StrategySetupResponse])
def read_strategy_setups(
    db: Annotated[Session, Depends(get_db)],
    state: StrategySetupState | None = None,
    eligible_only: bool = False,
    symbol: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[StrategySetupResponse]:
    normalized = validate_symbol(symbol) if symbol else None
    rows = StrategySetupRepository().list_setups(db, state, eligible_only, normalized, limit)
    return [StrategySetupResponse.model_validate(row) for row in rows]


@router.get("/setups/{setup_id}", response_model=StrategySetupResponse)
def read_strategy_setup(
    setup_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> StrategySetupResponse:
    row = StrategySetupRepository().get_by_setup_id(db, setup_id)
    if row is None:
        raise HTTPException(status_code=404, detail="setup not found")
    return StrategySetupResponse.model_validate(row)
