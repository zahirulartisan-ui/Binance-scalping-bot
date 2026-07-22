from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.logging import configure_logging
from app.core.settings import AppEnvironment, get_settings
from app.database.session import SessionLocal, verify_database_connectivity
from app.services.binance_client import BinanceMarketDataClient
from app.services.market_data_runner import MarketDataRunner
from app.services.migration_service import apply_migrations


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)
    app.state.database_available = False
    app.state.market_data_runner = None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "PATCH", "POST"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.on_event("startup")
    def verify_database_on_startup() -> None:
        if settings.app_env is AppEnvironment.TEST:
            app.state.database_available = True
            return
        try:
            apply_migrations(settings)
            app.state.database_available = verify_database_connectivity()
        except Exception:
            app.state.database_available = False
            if settings.effective_execution_enabled:
                raise
        if app.state.database_available and settings.market_data_collection_enabled:
            client = BinanceMarketDataClient(
                base_url=settings.binance_market_data_base_url,
                timeout_seconds=settings.binance_market_data_timeout_seconds,
                max_retries=settings.binance_market_data_max_retries,
                backoff_seconds=settings.binance_market_data_backoff_seconds,
            )
            runner = MarketDataRunner(settings, SessionLocal, client)
            app.state.market_data_runner = runner
            runner.start()

    @app.on_event("shutdown")
    def stop_market_data_runner() -> None:
        runner = app.state.market_data_runner
        if runner is not None:
            runner.stop()

    return app


app = create_app()
