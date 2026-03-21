from fastapi import APIRouter

from app.api.endpoints.health import router as health_router
from app.api.endpoints.pipeline import router as pipeline_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(pipeline_router, tags=["pipeline"])
