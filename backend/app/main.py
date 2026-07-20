from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.logging import configure_logging
from app.core.settings import AppEnvironment, get_settings
from app.database.session import verify_database_connectivity


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)
    app.state.database_available = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "PATCH"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.on_event("startup")
    def verify_database_on_startup() -> None:
        if settings.app_env is AppEnvironment.TEST:
            app.state.database_available = True
            return
        try:
            app.state.database_available = verify_database_connectivity()
        except Exception:
            app.state.database_available = False
            if settings.effective_execution_enabled:
                raise

    return app


app = create_app()
