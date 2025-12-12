"""Request models for API endpoints."""
from typing import Optional, Literal

from pydantic import BaseModel, Field


class GenieQueryRequest(BaseModel):
    """Request model for Genie chat queries."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to ask Genie",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Existing conversation ID for follow-up questions",
    )
    persona: Literal["executive", "manager", "rep"] = Field(
        default="executive",
        description="User persona for tailored responses",
    )
    use_ai_orchestration: bool = Field(
        default=True,
        description="Use Claude AI for question decomposition and interpretation",
    )


class RegenerateRequest(BaseModel):
    """Request model for regenerating a Genie response."""

    message_id: str = Field(
        ...,
        description="The message ID to regenerate",
    )


class DashboardFilter(BaseModel):
    """Filter options for dashboard queries."""

    date_range: Literal["last_7_days", "last_30_days", "last_90_days", "ytd"] = Field(
        default="last_30_days",
        description="Time range for data filtering",
    )
    territory: Optional[str] = Field(
        None,
        description="Territory ID to filter by",
    )
    rep_id: Optional[str] = Field(
        None,
        description="Rep ID for rep-specific dashboards",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of records to return",
    )


class TerritoryFilter(BaseModel):
    """Filter options for territory-specific queries."""

    territory_id: str = Field(
        ...,
        description="Territory ID to filter by",
    )
    date_range: Literal["last_7_days", "last_30_days", "last_90_days", "ytd"] = Field(
        default="last_30_days",
        description="Time range for data filtering",
    )
