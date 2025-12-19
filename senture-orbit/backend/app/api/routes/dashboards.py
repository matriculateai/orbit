"""Dashboard API endpoints."""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_postgres, get_redis
from app.models.responses import (
    DashboardResponse,
    ExecutiveDashboardResponse,
    ManagerDashboardResponse,
    RepDashboardResponse,
)
from app.services.postgres import PostgresService
from app.services.redis_service import RedisService
from app.services.persona_formatter import PersonaFormatter

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Executive Dashboard ====================


@router.get("/executive/overview", response_model=ExecutiveDashboardResponse)
async def get_executive_overview(
    date_range: str = Query(
        default="last_30_days",
        description="Time range filter",
        pattern="^(last_7_days|last_30_days|last_90_days|ytd)$",
    ),
    postgres: PostgresService = Depends(get_postgres),
    redis: Optional[RedisService] = Depends(get_redis),
) -> ExecutiveDashboardResponse:
    """Get executive dashboard overview with KPIs and top opportunities.

    Returns:
    - Total sales, active customers, opportunity value, critical gaps
    - Sales trend data for charts
    - Top 10 stock opportunities
    """
    try:
        # Check cache
        cache_key = None
        if redis:
            cache_key = redis.generate_cache_key(f"exec_overview:{date_range}")
            cached = await redis.get_cached_result(cache_key)
            if cached:
                return ExecutiveDashboardResponse(**cached)

        # Build date filter based on date_range
        if date_range == "last_7_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '7 days'"
        elif date_range == "last_30_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '30 days'"
        elif date_range == "last_90_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '90 days'"
        else:  # ytd
            date_filter = "date_key >= DATE_TRUNC('year', CURRENT_DATE)"

        # Get KPIs
        kpis_query = f"""
        SELECT
            COALESCE(SUM(secondary_value), 0) as total_sales,
            COUNT(DISTINCT customer_id) as active_customers,
            (SELECT COALESCE(SUM(opportunity_value), 0)
             FROM agg.kpi_dashboard
             WHERE dsoh_days < 45 AND opportunity_value > 0) as opportunity_value,
            (SELECT COUNT(*)
             FROM agg.kpi_dashboard
             WHERE dsoh_days < 14 AND opportunity_value > 0) as critical_gaps
        FROM fact.secondary_sales_daily
        WHERE {date_filter}
        """
        kpis_result = await postgres.execute_query(kpis_query, fetch_all=False)
        kpis_data = kpis_result[0] if kpis_result else {}

        # Get sales trend (daily for charts)
        trend_query = f"""
        SELECT
            date_key as date,
            SUM(secondary_value) as sales
        FROM fact.secondary_sales_daily
        WHERE {date_filter}
        GROUP BY date_key
        ORDER BY date_key
        """
        sales_trend = await postgres.execute_query(trend_query)

        # Get top 10 opportunities
        opps_query = """
        SELECT
            product_code,
            product_name,
            brand,
            customer_name,
            customer_group,
            region,
            soh,
            avg_daily_units,
            dsoh_days,
            ideal_stock_45d_units,
            opportunity_units,
            opportunity_value
        FROM agg.kpi_dashboard
        WHERE dsoh_days < 45 AND opportunity_value > 0
        ORDER BY opportunity_value DESC
        LIMIT 10
        """
        opportunities = await postgres.execute_query(opps_query)

        # Format KPIs
        from app.models.responses import KPIData
        kpis = KPIData(
            total_sales=float(kpis_data.get("total_sales", 0)),
            active_customers=int(kpis_data.get("active_customers", 0)),
            opportunity_value=float(kpis_data.get("opportunity_value", 0)),
            critical_gaps=int(kpis_data.get("critical_gaps", 0)),
            sales_trend=sales_trend,
            period=date_range,
        )

        response_data = {
            "kpis": kpis,
            "top_opportunities": opportunities,
            "sales_trend": sales_trend,
            "success": True,
        }

        # Cache result
        if redis and cache_key:
            await redis.cache_result(cache_key, response_data, ttl=1800)

        return ExecutiveDashboardResponse(**response_data)

    except Exception as e:
        logger.error(f"Error getting executive dashboard: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve executive dashboard: {str(e)}",
        )


@router.get("/executive/kpis")
async def get_executive_kpis(
    date_range: str = Query(default="last_30_days"),
    postgres: PostgresService = Depends(get_postgres),
) -> Dict[str, Any]:
    """Get executive KPIs only."""
    try:
        # Build date filter
        if date_range == "last_7_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '7 days'"
        elif date_range == "last_30_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '30 days'"
        elif date_range == "last_90_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '90 days'"
        else:  # ytd
            date_filter = "date_key >= DATE_TRUNC('year', CURRENT_DATE)"

        query = f"""
        SELECT
            COALESCE(SUM(secondary_value), 0) as total_sales,
            COUNT(DISTINCT customer_id) as active_customers,
            (SELECT COALESCE(SUM(opportunity_value), 0)
             FROM agg.kpi_dashboard
             WHERE dsoh_days < 45 AND opportunity_value > 0) as opportunity_value,
            (SELECT COUNT(*)
             FROM agg.kpi_dashboard
             WHERE dsoh_days < 14 AND opportunity_value > 0) as critical_gaps
        FROM fact.secondary_sales_daily
        WHERE {date_filter}
        """
        result = await postgres.execute_query(query, fetch_all=False)
        kpis = result[0] if result else {}

        return {"success": True, "data": kpis}
    except Exception as e:
        logger.error(f"Error getting executive KPIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executive/sales-trend")
async def get_sales_trend(
    date_range: str = Query(default="last_90_days"),
    granularity: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    postgres: PostgresService = Depends(get_postgres),
) -> Dict[str, Any]:
    """Get sales trend data for charts."""
    try:
        # Build date filter
        if date_range == "last_7_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '7 days'"
        elif date_range == "last_30_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '30 days'"
        elif date_range == "last_90_days":
            date_filter = "date_key >= CURRENT_DATE - INTERVAL '90 days'"
        else:  # ytd
            date_filter = "date_key >= DATE_TRUNC('year', CURRENT_DATE)"

        # Build grouping based on granularity
        if granularity == "daily":
            group_by = "date_key"
            select_date = "date_key as date"
        elif granularity == "weekly":
            group_by = "DATE_TRUNC('week', date_key)"
            select_date = "DATE_TRUNC('week', date_key) as date"
        else:  # monthly
            group_by = "DATE_TRUNC('month', date_key)"
            select_date = "DATE_TRUNC('month', date_key) as date"

        query = f"""
        SELECT
            {select_date},
            SUM(secondary_value) as sales
        FROM fact.secondary_sales_daily
        WHERE {date_filter}
        GROUP BY {group_by}
        ORDER BY {group_by}
        """
        trend = await postgres.execute_query(query)

        return {"success": True, "data": trend}
    except Exception as e:
        logger.error(f"Error getting sales trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Manager Dashboard ====================
# Coming soon - will be migrated in future release


@router.get("/manager/territory/{territory_id}")
async def get_manager_territory(
    territory_id: str,
    date_range: str = Query(default="last_30_days"),
) -> Dict[str, Any]:
    """Manager dashboard - Coming soon.

    This endpoint will be available in a future release with:
    - Product performance in territory
    - Rep performance rankings
    - Stock opportunities by territory
    """
    return {
        "success": True,
        "message": "Manager dashboard coming soon",
        "status": "not_implemented",
        "territory_id": territory_id,
        "available_features": [
            "Product performance tracking",
            "Rep performance rankings",
            "Territory-specific opportunities",
        ]
    }


@router.get("/manager/territories")
async def list_territories() -> Dict[str, Any]:
    """List territories - Coming soon."""
    return {
        "success": True,
        "message": "Territory listing coming soon",
        "status": "not_implemented",
    }


@router.get("/manager/rep-performance")
async def get_rep_performance(
    territory_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Rep performance by territory - Coming soon."""
    return {
        "success": True,
        "message": "Rep performance dashboard coming soon",
        "status": "not_implemented",
        "territory_id": territory_id,
    }


# ==================== Rep Dashboard ====================
# Coming soon - will be migrated in future release


@router.get("/rep/opportunities")
async def get_rep_opportunities(
    rep_id: str = Query(..., description="Rep ID"),
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """Rep dashboard - Coming soon.

    This endpoint will be available in a future release with:
    - Personal performance metrics
    - Priority opportunities
    - Territory-specific insights
    """
    return {
        "success": True,
        "message": "Rep dashboard coming soon",
        "status": "not_implemented",
        "rep_id": rep_id,
        "available_features": [
            "Personal performance tracking",
            "Priority opportunities",
            "Customer call history",
            "Territory insights",
        ]
    }


@router.get("/rep/my-performance")
async def get_my_performance(
    rep_id: str = Query(..., description="Rep ID"),
) -> Dict[str, Any]:
    """Rep performance metrics - Coming soon."""
    return {
        "success": True,
        "message": "Rep performance metrics coming soon",
        "status": "not_implemented",
        "rep_id": rep_id,
    }


# ==================== Generic Dashboard Endpoint ====================


@router.get("/{dashboard_type}")
async def get_dashboard(
    dashboard_type: str,
    date_range: str = Query(default="last_30_days"),
    territory: Optional[str] = Query(None),
    rep_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Generic dashboard endpoint that routes to specific dashboard types.

    Currently supported:
    - executive: Fully migrated to PostgreSQL
    - manager: Coming soon
    - rep: Coming soon
    """
    if dashboard_type == "executive":
        return {
            "success": True,
            "dashboard_type": "executive",
            "message": "Use /executive/overview endpoint for full executive dashboard",
            "status": "available",
        }

    elif dashboard_type == "manager":
        return {
            "success": True,
            "dashboard_type": "manager",
            "message": "Manager dashboard coming soon",
            "status": "not_implemented",
        }

    elif dashboard_type == "rep":
        return {
            "success": True,
            "dashboard_type": "rep",
            "message": "Rep dashboard coming soon",
            "status": "not_implemented",
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dashboard type: {dashboard_type}. Valid types: executive, manager, rep",
        )
