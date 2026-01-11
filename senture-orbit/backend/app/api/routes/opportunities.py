"""Stock opportunities API endpoints."""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.services.databricks import DatabricksService, sanitize_identifier, sanitize_string_value
from app.services.persona_formatter import PersonaFormatter

router = APIRouter()
logger = logging.getLogger(__name__)


def get_databricks_service(
    settings: Settings = Depends(get_settings),
) -> DatabricksService:
    """Dependency for Databricks service."""
    return DatabricksService(settings)


@router.get("/")
async def get_opportunities(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    region: Optional[str] = Query(None, description="Filter by region"),
    min_value: Optional[float] = Query(None, description="Minimum opportunity value"),
    max_dsoh: Optional[int] = Query(
        default=45, description="Maximum days stock on hand"
    ),
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get stock opportunities with optional filters.

    Returns opportunities where DSOH < threshold and there's positive value.
    """
    try:
        settings = get_settings()

        # Build filters
        filters = [f"dsoh_days < {max_dsoh}", "opportunity_value > 0"]

        if region:
            safe_region = sanitize_identifier(region, "region")
            filters.append(f"region = '{safe_region}'")

        if min_value:
            filters.append(f"opportunity_value >= {min_value}")

        where_clause = " AND ".join(filters)

        query = f"""
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
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
        WHERE {where_clause}
        ORDER BY opportunity_value DESC
        LIMIT {limit}
        """

        results = await db.execute_query(query)
        db.close()

        # Calculate summary stats
        total_value = sum(r.get("opportunity_value", 0) for r in results)
        critical_count = sum(1 for r in results if r.get("dsoh_days", 0) < 14)

        return {
            "success": True,
            "total_count": len(results),
            "total_value": total_value,
            "critical_count": critical_count,
            "opportunities": results,
        }

    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve opportunities: {str(e)}",
        )


@router.get("/summary")
async def get_opportunities_summary(
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get summary statistics for all opportunities."""
    try:
        settings = get_settings()

        query = f"""
        SELECT
            COUNT(*) as total_opportunities,
            SUM(opportunity_value) as total_value,
            SUM(CASE WHEN dsoh_days < 14 THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN dsoh_days >= 14 AND dsoh_days < 30 THEN 1 ELSE 0 END) as warning_count,
            SUM(CASE WHEN dsoh_days >= 30 AND dsoh_days < 45 THEN 1 ELSE 0 END) as moderate_count,
            AVG(dsoh_days) as avg_dsoh,
            COUNT(DISTINCT customer_name) as affected_customers,
            COUNT(DISTINCT product_code) as affected_products
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
        WHERE dsoh_days < 45 AND opportunity_value > 0
        """

        results = await db.execute_query(query)
        db.close()

        if not results:
            return {"success": True, "summary": None}

        summary = results[0]
        return {
            "success": True,
            "summary": {
                "total_opportunities": int(summary.get("total_opportunities", 0)),
                "total_value": float(summary.get("total_value", 0)),
                "critical_count": int(summary.get("critical_count", 0)),
                "warning_count": int(summary.get("warning_count", 0)),
                "moderate_count": int(summary.get("moderate_count", 0)),
                "avg_dsoh": float(summary.get("avg_dsoh", 0)),
                "affected_customers": int(summary.get("affected_customers", 0)),
                "affected_products": int(summary.get("affected_products", 0)),
            },
        }

    except Exception as e:
        logger.error(f"Error getting opportunities summary: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve opportunities summary: {str(e)}",
        )


@router.get("/by-region")
async def get_opportunities_by_region(
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get opportunity breakdown by region."""
    try:
        settings = get_settings()

        query = f"""
        SELECT
            region,
            COUNT(*) as opportunity_count,
            SUM(opportunity_value) as total_value,
            SUM(CASE WHEN dsoh_days < 14 THEN 1 ELSE 0 END) as critical_count,
            AVG(dsoh_days) as avg_dsoh
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
        WHERE dsoh_days < 45 AND opportunity_value > 0
        GROUP BY region
        ORDER BY total_value DESC
        """

        results = await db.execute_query(query)
        db.close()

        return {
            "success": True,
            "regions": results,
        }

    except Exception as e:
        logger.error(f"Error getting opportunities by region: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve regional opportunities: {str(e)}",
        )


@router.get("/by-brand")
async def get_opportunities_by_brand(
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get opportunity breakdown by brand."""
    try:
        settings = get_settings()

        query = f"""
        SELECT
            brand,
            COUNT(*) as opportunity_count,
            SUM(opportunity_value) as total_value,
            SUM(CASE WHEN dsoh_days < 14 THEN 1 ELSE 0 END) as critical_count,
            AVG(dsoh_days) as avg_dsoh
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
        WHERE dsoh_days < 45 AND opportunity_value > 0
        GROUP BY brand
        ORDER BY total_value DESC
        """

        results = await db.execute_query(query)
        db.close()

        return {
            "success": True,
            "brands": results,
        }

    except Exception as e:
        logger.error(f"Error getting opportunities by brand: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve brand opportunities: {str(e)}",
        )


@router.get("/customer/{customer_name}")
async def get_customer_opportunities(
    customer_name: str,
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get all opportunities for a specific customer."""
    try:
        settings = get_settings()
        safe_customer_name = sanitize_string_value(customer_name, "customer_name")

        query = f"""
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
        FROM {settings.DATABRICKS_CATALOG}.{settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
        WHERE customer_name = '{safe_customer_name}'
            AND dsoh_days < 45
            AND opportunity_value > 0
        ORDER BY opportunity_value DESC
        """

        results = await db.execute_query(query)
        db.close()

        total_value = sum(r.get("opportunity_value", 0) for r in results)

        return {
            "success": True,
            "customer_name": customer_name,
            "total_value": total_value,
            "opportunity_count": len(results),
            "opportunities": results,
        }

    except Exception as e:
        logger.error(f"Error getting customer opportunities: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve customer opportunities: {str(e)}",
        )


@router.get("/priority")
async def get_priority_opportunities(
    persona: str = Query(
        default="executive",
        description="User persona for priority ranking",
        regex="^(executive|manager|rep)$",
    ),
    limit: int = Query(default=10, ge=1, le=50),
    region: Optional[str] = Query(None),
    db: DatabricksService = Depends(get_databricks_service),
) -> Dict[str, Any]:
    """Get prioritized opportunities based on persona.

    Executive: Highest value opportunities
    Manager: Mix of critical and high-value in region
    Rep: Immediately actionable opportunities
    """
    try:
        opportunities = await db.get_top_opportunities(limit=limit, region=region)
        db.close()

        # Apply persona-specific formatting and insights
        formatter = PersonaFormatter(persona)
        formatted = formatter.format_opportunities(opportunities, persona)

        return {
            "success": True,
            "persona": persona,
            **formatted,
        }

    except Exception as e:
        logger.error(f"Error getting priority opportunities: {e}")
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve priority opportunities: {str(e)}",
        )
