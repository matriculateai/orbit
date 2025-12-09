"""Dashboard API endpoints."""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.models.responses import (
    DashboardResponse,
    ExecutiveDashboardResponse,
    ManagerDashboardResponse,
    RepDashboardResponse,
)
from app.services.databricks import DatabricksService
from app.services.persona_formatter import PersonaFormatter

router = APIRouter()
logger = logging.getLogger(__name__)


def get_databricks_service(
    settings: Settings = Depends(get_settings),
) -> DatabricksService:
    """Dependency for Databricks service."""
    return DatabricksService(settings)


# ==================== Executive Dashboard ====================


@router.get("/executive/overview", response_model=ExecutiveDashboardResponse)
async def get_executive_overview(
    date_range: str = Query(
        default="last_30_days",
        description="Time range filter",
        regex="^(last_7_days|last_30_days|last_90_days|ytd)$",
    ),
    db: DatabricksService = Depends(get_databricks_service),
) -> ExecutiveDashboardResponse:
    """Get executive dashboard overview with KPIs and top opportunities.

    Returns:
    - Total sales, active customers, opportunity value, critical gaps
    - Sales trend data for charts
    - Top 10 stock opportunities
    """
    try:
        # Get KPIs
        kpis_data = await db.get_executive_kpis(date_range)

        # Get sales trend
        sales_trend = await db.get_sales_trend(date_range, granularity="daily")

        # Get top opportunities
        opportunities = await db.get_top_opportunities(limit=10)

        # Format with persona insights
        formatter = PersonaFormatter("executive")
        formatted_kpis = formatter.format_kpis(kpis_data, "executive")

        db.close()

        return ExecutiveDashboardResponse(
            kpis=formatted_kpis,
            top_opportunities=opportunities,
            sales_trend=sales_trend,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting executive dashboard: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve executive dashboard: {str(e)}",
        )


@router.get("/executive/kpis")
async def get_executive_kpis(
    date_range: str = Query(default="last_30_days"),
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get executive KPIs only."""
    try:
        kpis = await db.get_executive_kpis(date_range)
        db.close()
        return {"success": True, "data": kpis}
    except Exception as e:
        logger.error(f"Error getting executive KPIs: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executive/sales-trend")
async def get_sales_trend(
    date_range: str = Query(default="last_90_days"),
    granularity: str = Query(default="daily", regex="^(daily|weekly|monthly)$"),
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get sales trend data for charts."""
    try:
        trend = await db.get_sales_trend(date_range, granularity)
        db.close()
        return {"success": True, "data": trend}
    except Exception as e:
        logger.error(f"Error getting sales trend: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Manager Dashboard ====================


@router.get("/manager/territory/{territory_id}", response_model=ManagerDashboardResponse)
async def get_manager_territory(
    territory_id: str,
    date_range: str = Query(default="last_30_days"),
    db: DatabricksService = Depends(get_databricks_service),
) -> ManagerDashboardResponse:
    """Get manager dashboard for a specific territory.

    Returns:
    - Product performance in territory
    - Rep performance rankings
    - Stock opportunities in territory
    """
    try:
        territory_data = await db.get_territory_data(territory_id, date_range)

        # Format with persona insights
        formatter = PersonaFormatter("manager")
        formatted_opps = formatter.format_opportunities(
            territory_data.get("opportunities", []),
            "manager",
        )

        db.close()

        return ManagerDashboardResponse(
            territory_id=territory_id,
            product_performance=territory_data.get("product_performance", []),
            rep_performance=territory_data.get("rep_performance", []),
            opportunities=territory_data.get("opportunities", []),
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting manager dashboard: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve manager dashboard: {str(e)}",
        )


@router.get("/manager/territories")
async def list_territories(
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """List all available territories."""
    try:
        settings = get_settings()
        query = f"""
        SELECT DISTINCT territory, region
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.dim_rep
        WHERE territory IS NOT NULL
        ORDER BY region, territory
        """
        territories = await db.execute_query(query)
        db.close()
        return {"success": True, "territories": territories}
    except Exception as e:
        logger.error(f"Error listing territories: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/manager/rep-performance")
async def get_rep_performance(
    territory_id: Optional[str] = Query(None),
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get rep performance data, optionally filtered by territory."""
    try:
        settings = get_settings()
        territory_filter = f"AND r.territory = '{territory_id}'" if territory_id else ""

        query = f"""
        SELECT
            r.rep_id,
            r.rep_name,
            a.coverage_percent,
            a.strike_rate,
            a.total_calls,
            r.territory,
            r.region
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.fact_rep_activity_monthly a
        JOIN {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.dim_rep r
            ON a.rep_id = r.rep_id
        WHERE a.yyyymm = DATE_FORMAT(CURRENT_DATE - INTERVAL 1 MONTH, 'yyyyMM')
            {territory_filter}
        ORDER BY a.strike_rate DESC
        """
        reps = await db.execute_query(query)
        db.close()
        return {"success": True, "data": reps}
    except Exception as e:
        logger.error(f"Error getting rep performance: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Rep Dashboard ====================


@router.get("/rep/opportunities", response_model=RepDashboardResponse)
async def get_rep_opportunities(
    rep_id: str = Query(..., description="Rep ID"),
    limit: int = Query(default=20, ge=1, le=100),
    db: DatabricksService = Depends(get_databricks_service),
) -> RepDashboardResponse:
    """Get rep dashboard with prioritized opportunities.

    Returns:
    - Rep's personal performance metrics
    - Priority opportunities (top 5 by value)
    - All opportunities in rep's territory
    """
    try:
        rep_data = await db.get_rep_dashboard_data(rep_id, limit)

        # Format with persona insights
        formatter = PersonaFormatter("rep")
        formatted_opps = formatter.format_opportunities(
            rep_data.get("all_opportunities", []),
            "rep",
        )

        db.close()

        return RepDashboardResponse(
            rep_id=rep_id,
            my_performance=rep_data.get("my_performance"),
            priority_opportunities=rep_data.get("priority_opportunities", []),
            all_opportunities=rep_data.get("all_opportunities", []),
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting rep dashboard: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve rep dashboard: {str(e)}",
        )


@router.get("/rep/my-performance")
async def get_my_performance(
    rep_id: str = Query(..., description="Rep ID"),
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get performance metrics for a specific rep."""
    try:
        settings = get_settings()
        query = f"""
        SELECT
            r.rep_id,
            r.rep_name,
            a.coverage_percent,
            a.strike_rate,
            a.total_calls,
            r.territory,
            r.region
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.fact_rep_activity_monthly a
        JOIN {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.dim_rep r
            ON a.rep_id = r.rep_id
        WHERE r.rep_id = '{rep_id}'
            AND a.yyyymm = DATE_FORMAT(CURRENT_DATE - INTERVAL 1 MONTH, 'yyyyMM')
        """
        results = await db.execute_query(query)
        db.close()

        if not results:
            return {"success": True, "data": None, "message": "No performance data found"}

        return {"success": True, "data": results[0]}
    except Exception as e:
        logger.error(f"Error getting rep performance: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Generic Dashboard Endpoint ====================


@router.get("/{dashboard_type}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_type: str,
    date_range: str = Query(default="last_30_days"),
    territory: Optional[str] = Query(None),
    rep_id: Optional[str] = Query(None),
    db: DatabricksService = Depends(get_databricks_service),
) -> DashboardResponse:
    """Generic dashboard endpoint that routes to specific dashboard types."""
    try:
        if dashboard_type == "executive":
            kpis = await db.get_executive_kpis(date_range)
            opportunities = await db.get_top_opportunities(limit=10)
            data = {"kpis": kpis, "opportunities": opportunities}

        elif dashboard_type == "manager" and territory:
            data = await db.get_territory_data(territory, date_range)

        elif dashboard_type == "rep" and rep_id:
            data = await db.get_rep_dashboard_data(rep_id)

        else:
            db.close()
            raise HTTPException(
                status_code=400,
                detail=f"Invalid dashboard type or missing parameters",
            )

        db.close()
        return DashboardResponse(
            dashboard_type=dashboard_type,
            data=data,
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=str(e))
