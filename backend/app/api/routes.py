from fastapi import APIRouter

from app.api.v1.execution import router as execution_router
from app.api.v1.health import router as health_router
from app.api.v1.market_data import router as market_data_router
from app.api.v1.regime import router as regime_router
from app.api.v1.scanner import router as scanner_router
from app.api.v1.settings import router as settings_router
from app.api.v1.signals import router as signals_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.trades import router as trades_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(execution_router)
api_router.include_router(market_data_router)
api_router.include_router(regime_router)
api_router.include_router(scanner_router)
api_router.include_router(settings_router)
api_router.include_router(signals_router)
api_router.include_router(strategies_router)
api_router.include_router(trades_router)
