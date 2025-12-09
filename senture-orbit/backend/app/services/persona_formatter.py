"""Persona-based response formatter for Genie responses.

Formats Genie responses based on user persona (Executive, Manager, Rep)
to provide contextually appropriate insights and recommendations.
"""
from typing import Any, Dict, List, Optional


class PersonaFormatter:
    """Format Genie responses based on user persona."""

    # Persona types
    EXECUTIVE = "executive"
    MANAGER = "manager"
    REP = "rep"

    def __init__(self, persona: str = "executive"):
        """Initialize the formatter.

        Args:
            persona: User persona type
        """
        self.persona = persona.lower()

    def format_opportunities(
        self,
        opportunities: List[Dict[str, Any]],
        persona: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format opportunity data based on persona.

        Args:
            opportunities: List of opportunity dictionaries
            persona: Optional persona override

        Returns:
            Formatted opportunity response
        """
        persona = persona or self.persona

        if not opportunities:
            return {
                "summary": "No stock opportunities found.",
                "opportunities": [],
                "insights": [],
            }

        total_value = sum(opp.get("opportunity_value", 0) for opp in opportunities)
        critical_count = sum(1 for opp in opportunities if opp.get("dsoh_days", 0) < 14)

        insights = []

        if persona == self.EXECUTIVE:
            insights = self._executive_insights(opportunities, total_value, critical_count)
        elif persona == self.MANAGER:
            insights = self._manager_insights(opportunities, total_value, critical_count)
        else:  # Rep
            insights = self._rep_insights(opportunities, total_value, critical_count)

        return {
            "summary": f"Found {len(opportunities)} opportunities worth ${total_value:,.2f}",
            "total_value": total_value,
            "critical_count": critical_count,
            "opportunities": opportunities,
            "insights": insights,
        }

    def _executive_insights(
        self,
        opportunities: List[Dict[str, Any]],
        total_value: float,
        critical_count: int,
    ) -> List[str]:
        """Generate executive-level insights."""
        insights = []

        # Regional analysis
        regions = {}
        for opp in opportunities:
            region = opp.get("region", "Unknown")
            regions[region] = regions.get(region, 0) + opp.get("opportunity_value", 0)

        top_region = max(regions.items(), key=lambda x: x[1]) if regions else None
        if top_region:
            insights.append(
                f"{top_region[0]} region has the highest opportunity value at ${top_region[1]:,.2f}"
            )

        # Brand analysis
        brands = {}
        for opp in opportunities:
            brand = opp.get("brand", "Unknown")
            brands[brand] = brands.get(brand, 0) + opp.get("opportunity_value", 0)

        if brands:
            top_brand = max(brands.items(), key=lambda x: x[1])
            insights.append(
                f"{top_brand[0]} brand represents ${top_brand[1]:,.2f} in opportunities"
            )

        if critical_count > 0:
            insights.append(
                f"{critical_count} locations have critically low stock (< 14 days)"
            )

        return insights

    def _manager_insights(
        self,
        opportunities: List[Dict[str, Any]],
        total_value: float,
        critical_count: int,
    ) -> List[str]:
        """Generate manager-level insights."""
        insights = []

        # Customer analysis
        customers = {}
        for opp in opportunities:
            customer = opp.get("customer_name", "Unknown")
            customers[customer] = customers.get(customer, 0) + opp.get("opportunity_value", 0)

        top_customers = sorted(customers.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_customers:
            insights.append(
                f"Top opportunity customers: {', '.join(c[0] for c in top_customers)}"
            )

        # Product analysis
        products = {}
        for opp in opportunities:
            product = opp.get("product_name", "Unknown")
            products[product] = products.get(product, 0) + 1

        if products:
            most_common = max(products.items(), key=lambda x: x[1])
            insights.append(
                f"{most_common[0]} appears in {most_common[1]} opportunities"
            )

        if critical_count > 0:
            critical_opps = [
                opp for opp in opportunities if opp.get("dsoh_days", 0) < 14
            ]
            urgent_value = sum(opp.get("opportunity_value", 0) for opp in critical_opps)
            insights.append(
                f"Urgent action needed: {critical_count} critical gaps worth ${urgent_value:,.2f}"
            )

        return insights

    def _rep_insights(
        self,
        opportunities: List[Dict[str, Any]],
        total_value: float,
        critical_count: int,
    ) -> List[str]:
        """Generate rep-level actionable insights."""
        insights = []

        if not opportunities:
            return ["No immediate opportunities in your territory."]

        # Prioritization
        top_opp = opportunities[0] if opportunities else None
        if top_opp:
            insights.append(
                f"Priority: Visit {top_opp.get('customer_name')} for "
                f"{top_opp.get('product_name')} (${top_opp.get('opportunity_value', 0):,.2f})"
            )

        # Quick wins (medium DSOH, high value)
        quick_wins = [
            opp for opp in opportunities
            if 14 <= opp.get("dsoh_days", 0) <= 30 and opp.get("opportunity_value", 0) > 1000
        ]
        if quick_wins:
            insights.append(
                f"{len(quick_wins)} quick win opportunities available"
            )

        if critical_count > 0:
            insights.append(
                f"Alert: {critical_count} customers need immediate attention (< 14 days stock)"
            )

        return insights

    def format_kpis(
        self,
        kpis: Dict[str, Any],
        persona: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format KPIs with persona-specific context.

        Args:
            kpis: KPI dictionary
            persona: Optional persona override

        Returns:
            Formatted KPIs with insights
        """
        persona = persona or self.persona

        formatted = {**kpis}

        # Add persona-specific highlights
        if persona == self.EXECUTIVE:
            formatted["highlights"] = [
                f"Total addressable opportunity: ${kpis.get('opportunity_value', 0):,.2f}",
                f"Active customer base: {kpis.get('active_customers', 0):,}",
            ]
        elif persona == self.MANAGER:
            formatted["highlights"] = [
                f"Territory potential: ${kpis.get('opportunity_value', 0):,.2f}",
                f"Critical gaps requiring attention: {kpis.get('critical_gaps', 0)}",
            ]
        else:  # Rep
            formatted["highlights"] = [
                f"Your opportunity value: ${kpis.get('opportunity_value', 0):,.2f}",
                f"Action items: {kpis.get('critical_gaps', 0)} urgent visits needed",
            ]

        return formatted

    def get_suggested_questions(self, persona: Optional[str] = None) -> List[str]:
        """Get persona-specific suggested questions for Genie.

        Args:
            persona: Optional persona override

        Returns:
            List of suggested questions
        """
        persona = persona or self.persona

        if persona == self.EXECUTIVE:
            return [
                "What is our total sales performance this quarter?",
                "Which regions have the most stock opportunities?",
                "Show me the top 10 opportunities by value",
                "What is our customer coverage rate?",
                "Which brands are underperforming?",
            ]
        elif persona == self.MANAGER:
            return [
                "Show me my territory's performance this month",
                "Which reps have the highest strike rate?",
                "What are the critical stock gaps in my territory?",
                "Compare product performance across my team",
                "Which customers haven't been visited recently?",
            ]
        else:  # Rep
            return [
                "What are my priority visits for today?",
                "Which of my customers have low stock?",
                "Show me my performance metrics",
                "What products should I focus on?",
                "Which customers have the highest opportunity value?",
            ]
