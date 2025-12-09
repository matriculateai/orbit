"""API module for Senture Orbit."""
from fastapi import APIRouter

from app.api.routes import dashboards, genie_chat, health, opportunities

api_router = APIRouter()

# Include route modules
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(
    dashboards.router,
    prefix="/api/v1/dashboards",
    tags=["Dashboards"],
)
api_router.include_router(
    genie_chat.router,
    prefix="/api/v1/genie",
    tags=["Genie Chat"],
)
api_router.include_router(
    opportunities.router,
    prefix="/api/v1/opportunities",
    tags=["Opportunities"],
)
