from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.settings import router as settings_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(settings_router)
