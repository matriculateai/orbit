"""API module for Senture Orbit."""
from fastapi import APIRouter

from app.api.routes import chat, dashboards, genie_chat, health, opportunities

api_router = APIRouter()

# Include route modules
api_router.include_router(health.router, tags=["Health"])

# New Claude-powered chat endpoint (replaces Genie)
api_router.include_router(
    chat.router,
    prefix="/api/v1/chat",
    tags=["AI Chat"],
)

# Legacy Genie endpoint (deprecated, will be removed)
api_router.include_router(
    genie_chat.router,
    prefix="/api/v1/genie",
    tags=["Genie Chat (Deprecated)"],
)

api_router.include_router(
    dashboards.router,
    prefix="/api/v1/dashboards",
    tags=["Dashboards"],
)
api_router.include_router(
    opportunities.router,
    prefix="/api/v1/opportunities",
    tags=["Opportunities"],
)
