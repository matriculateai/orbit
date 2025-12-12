"""AI Orchestrator service for intelligent query processing.

This service coordinates between Claude AI and Databricks Genie to:
1. Decompose business questions into data sub-questions
2. Get SQL queries from Genie for each sub-question
3. Execute SQL and gather results
4. Use Claude to interpret results and generate persona-tailored responses
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import anthropic

from app.config import Settings
from app.services.databricks import DatabricksService
from app.services.genie_client import GenieClient

logger = logging.getLogger(__name__)

# Gold layer schema context for Claude
SCHEMA_CONTEXT = """
You have access to a pharmaceutical commercial intelligence database with the following tables:

## Dimension Tables

### dim_customer
Customer master data.
| Column | Type | Description |
|--------|------|-------------|
| customer_id | string | Unique customer identifier |
| customer_name | string | Customer name |
| customer_key | string | Customer key |
| customer_type | string | Type of customer |
| customer_group | string | Customer grouping |
| country | string | Country |
| province | string | Province |
| region | string | Region (e.g., "Gauteng", "Western Cape") |
| sub_region | string | Sub-region |
| town | string | Town |
| suburb | string | Suburb |
| speciality | string | Medical speciality |

### dim_product
Product master data.
| Column | Type | Description |
|--------|------|-------------|
| product_id | string | Unique product identifier |
| product_code | string | Product code |
| product_name | string | Product name |
| manufacturer_code | string | Manufacturer code |
| nappi_clean | string | NAPPI code (South African pharmaceutical ID) |
| brand | string | Brand name |
| product_group | string | Product grouping |
| category | string | Product category |

### dim_rep
Sales representative data.
| Column | Type | Description |
|--------|------|-------------|
| rep_id | string | Unique rep identifier |
| rep_code | string | Rep code |
| rep_name | string | Rep name |
| region | string | Region |
| territory | string | Territory |
| sra_code | string | SRA code |

### dim_date
Date dimension.
| Column | Type | Description |
|--------|------|-------------|
| date_key | date | Date key |
| year | int | Year |
| month | int | Month number |
| yyyymm | string | Year-month string (e.g., "202412") |
| month_name | string | Month name |
| quarter | int | Quarter number |

## Fact Tables

### fact_primary_sales_monthly
Primary sales (sell-in) by month.
| Column | Type | Description |
|--------|------|-------------|
| yyyymm | string | Year-month |
| product_id | string | Product ID |
| customer_id | string | Customer ID |
| primary_value | double | Primary sales value |
| qty_moved | double | Quantity moved |

### fact_secondary_sales_daily
Secondary sales (sell-out) by day.
| Column | Type | Description |
|--------|------|-------------|
| date_key | date | Date |
| product_id | string | Product ID |
| customer_id | string | Customer ID |
| delivered_qty | double | Delivered quantity |
| secondary_value | double | Secondary sales value |

### fact_stock_latest
Current stock levels.
| Column | Type | Description |
|--------|------|-------------|
| snapshot_date | date | Snapshot date |
| product_id | string | Product ID |
| customer_id | string | Customer ID |
| soh | double | Stock on hand |
| min_qty | double | Minimum quantity |
| max_qty | double | Maximum quantity |
| avg_sales | double | Average sales |

### fact_rep_activity_monthly
Rep activity metrics by month.
| Column | Type | Description |
|--------|------|-------------|
| rep_id | string | Rep ID |
| yyyymm | string | Year-month |
| total_calls | int | Total calls made |
| unique_calls | int | Unique calls |
| productive_calls | int | Productive calls |
| coverage_percent | double | Coverage percentage |
| workable_days | int | Workable days |
| days_worked | int | Days worked |
| strike_rate | double | Strike rate percentage |
| avg_calls_per_day | double | Average calls per day |
| customers_seen | int | Customers seen |
| appointments | int | Appointments |
| new_orders | int | New orders |
| written_value | double | Written value |

### fact_rep_calls_daily
Daily rep call details.
| Column | Type | Description |
|--------|------|-------------|
| date_key | date | Date |
| rep_id | string | Rep ID |
| customer_id | string | Customer ID |
| call_type | string | Type of call |
| visited | string | Whether visited |
| new_order | double | New order value |
| written_value | double | Written value |

### fact_backorders_monthly
Monthly backorder data.
| Column | Type | Description |
|--------|------|-------------|
| yyyymm | string | Year-month |
| product_id | string | Product ID |
| customer_id | string | Customer ID |
| qty | double | Quantity |
| volume | double | Volume |

### fact_targets_2025
2025 sales targets.
| Column | Type | Description |
|--------|------|-------------|
| product_id | string | Product ID |
| product_code | string | Product code |
| target_type | string | Target type |
| target_volume_2025 | double | Target volume for 2025 |
| target_value_2025 | double | Target value for 2025 |

## Materialized Views

### mv_kpi_dashboard
Pre-calculated KPIs for stock opportunities.
| Column | Type | Description |
|--------|------|-------------|
| product_code | string | Product code |
| product_name | string | Product name |
| brand | string | Brand |
| customer_name | string | Customer name |
| customer_group | string | Customer group |
| region | string | Region |
| soh | double | Stock on hand |
| avg_daily_units | double | Average daily units sold |
| dsoh_days | double | Days stock on hand |
| ideal_stock_45d_units | double | Ideal 45-day stock |
| opportunity_units | double | Opportunity in units |
| opportunity_value | double | Opportunity value in currency |

## Key Business Concepts
- **DSOH (Days Stock on Hand)**: How many days the current stock will last based on average sales
- **Stock Opportunity**: When DSOH < 45 days, there's an opportunity to sell more
- **Primary Sales**: Sell-in from manufacturer to distributor/pharmacy
- **Secondary Sales**: Sell-out from pharmacy to end consumer
- **Strike Rate**: Percentage of calls that result in orders
- **Coverage**: Percentage of target customers visited
"""

PERSONA_CONTEXTS = {
    "executive": """
You are presenting insights to a pharmaceutical executive (CEO, VP Sales, etc.).
Focus on:
- High-level strategic insights and trends
- Total opportunity value and revenue impact
- Regional performance comparisons
- Key risks and recommendations
- Use currency values and percentages
- Keep technical details minimal
""",
    "manager": """
You are presenting insights to a regional/territory sales manager.
Focus on:
- Territory-specific performance metrics
- Rep team performance and rankings
- Actionable opportunities in their region
- Customer and product-level details when relevant
- Performance against targets
- Specific recommendations for their team
""",
    "rep": """
You are presenting insights to a field sales representative.
Focus on:
- Specific customer opportunities they can act on today
- Clear, actionable next steps
- Simple explanations of which products to push
- Customer names and locations
- Stock levels and urgency indicators
- Keep it practical and immediately useful
"""
}


class AIOrchestrator:
    """Orchestrates AI-powered query processing using Claude and Genie."""

    MAX_SUB_QUESTIONS = 3

    def __init__(self, settings: Settings):
        """Initialize the orchestrator.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.claude = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.genie_client = GenieClient(settings)
        self.databricks = DatabricksService(settings)

    async def close(self) -> None:
        """Close all connections."""
        await self.genie_client.close()
        self.databricks.close()

    async def process_question(
        self,
        question: str,
        persona: str = "executive",
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a business question through the full AI pipeline.

        1. Use Claude to decompose the question into data sub-questions
        2. Send each sub-question to Genie to get SQL
        3. Execute SQL queries and collect results
        4. Use Claude to interpret results with persona context

        Args:
            question: The user's business question
            persona: User persona (executive, manager, rep)
            conversation_id: Optional existing conversation ID

        Returns:
            Complete response with interpretation and data
        """
        try:
            logger.info(f"Processing question for persona '{persona}': {question[:100]}...")

            # Step 1: Decompose question into data sub-questions
            sub_questions = await self._generate_sub_questions(question)
            logger.info(f"Generated {len(sub_questions)} sub-questions")

            # Step 2: Get SQL from Genie for each sub-question
            genie_results = []
            for i, sub_q in enumerate(sub_questions):
                logger.info(f"Processing sub-question {i+1}: {sub_q[:50]}...")
                result = await self._get_genie_response(sub_q, conversation_id)
                genie_results.append({
                    "sub_question": sub_q,
                    "sql_query": result.get("sql_query"),
                    "data": result.get("data"),
                    "columns": result.get("columns"),
                    "success": result.get("success", False),
                    "error": result.get("error"),
                })
                # Use the conversation ID from first response for subsequent queries
                if not conversation_id and result.get("conversation_id"):
                    conversation_id = result.get("conversation_id")

            # Step 3: Generate interpretation with Claude
            interpretation = await self._generate_interpretation(
                original_question=question,
                sub_questions_results=genie_results,
                persona=persona,
            )

            # Compile the final response
            all_data_sets = self._get_all_data_sets(genie_results)

            return {
                "conversation_id": conversation_id,
                "message_id": "",
                "response": interpretation,
                "original_question": question,
                "sub_questions": [r["sub_question"] for r in genie_results],
                "sql_queries": [r["sql_query"] for r in genie_results if r["sql_query"]],
                "data": self._merge_data_results(genie_results),
                "columns": self._get_all_columns(genie_results),
                "all_data_sets": all_data_sets,  # All query results
                "visualization": None,
                "thinking_steps": [r["sub_question"] for r in genie_results],
                "status": "COMPLETED",
                "success": True,
                "error": None,
                "truncated": False,
                "persona": persona,
            }

        except Exception as e:
            logger.error(f"Error in AI orchestration: {e}", exc_info=True)
            return {
                "conversation_id": conversation_id or "",
                "message_id": "",
                "response": f"I encountered an error processing your question: {str(e)}",
                "sql_query": None,
                "data": None,
                "columns": None,
                "visualization": None,
                "thinking_steps": None,
                "status": "FAILED",
                "success": False,
                "error": str(e),
                "truncated": False,
            }

    async def _generate_sub_questions(self, question: str) -> List[str]:
        """Use Claude to decompose a business question into data sub-questions.

        Args:
            question: The user's business question

        Returns:
            List of data sub-questions (max 3)
        """
        prompt = f"""You are a pharmaceutical data analyst. Given a business question, break it down into specific data queries that can be answered using SQL against a database.

{SCHEMA_CONTEXT}

The user asked: "{question}"

Generate up to {self.MAX_SUB_QUESTIONS} specific, focused data questions that will help answer this business question. Each question should:
1. Be answerable with a single SQL query
2. Reference specific tables/columns from the schema
3. Be clear and unambiguous

Return ONLY the questions, one per line, with no numbering or bullet points. If the question is simple enough to answer with one query, return just one question.

Questions:"""

        try:
            response = self.claude.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse the response into individual questions
            text = response.content[0].text.strip()
            questions = [q.strip() for q in text.split('\n') if q.strip()]

            # Limit to max sub-questions
            return questions[:self.MAX_SUB_QUESTIONS]

        except Exception as e:
            logger.error(f"Error generating sub-questions: {e}")
            # Fall back to using the original question
            return [question]

    async def _get_genie_response(
        self,
        question: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get SQL and data from Genie for a question.

        Args:
            question: The data question
            conversation_id: Optional conversation ID for follow-ups

        Returns:
            Genie response with SQL and data
        """
        try:
            return await self.genie_client.query(question, conversation_id)
        except Exception as e:
            logger.error(f"Genie query failed: {e}")
            return {
                "sql_query": None,
                "data": None,
                "columns": None,
                "success": False,
                "error": str(e),
            }

    async def _generate_interpretation(
        self,
        original_question: str,
        sub_questions_results: List[Dict[str, Any]],
        persona: str,
    ) -> str:
        """Use Claude to interpret results and generate a response.

        Args:
            original_question: The user's original question
            sub_questions_results: Results from each sub-question
            persona: User persona for tailoring the response

        Returns:
            Natural language interpretation
        """
        # Build context from results
        results_context = []
        for i, result in enumerate(sub_questions_results, 1):
            sub_q = result["sub_question"]
            sql = result.get("sql_query", "N/A")
            data = result.get("data", [])
            error = result.get("error")

            if error:
                results_context.append(f"""
Sub-question {i}: {sub_q}
Status: Failed - {error}
""")
            elif data:
                # Format data as a simple table (limit rows for context)
                data_preview = data[:10] if len(data) > 10 else data
                data_str = self._format_data_as_text(data_preview, result.get("columns", []))
                results_context.append(f"""
Sub-question {i}: {sub_q}
SQL Query: {sql}
Results ({len(data)} rows{', showing first 10' if len(data) > 10 else ''}):
{data_str}
""")
            else:
                results_context.append(f"""
Sub-question {i}: {sub_q}
SQL Query: {sql}
Results: No data returned
""")

        results_text = "\n".join(results_context)
        persona_context = PERSONA_CONTEXTS.get(persona, PERSONA_CONTEXTS["executive"])

        prompt = f"""You are an AI assistant for a pharmaceutical commercial intelligence platform called Senture Orbit.

{persona_context}

The user asked: "{original_question}"

To answer this question, we ran the following data queries:

{results_text}

Based on these results, provide a clear, insightful response that:
1. Directly answers the user's question
2. Highlights key findings and numbers
3. Provides actionable insights appropriate for the {persona} persona
4. Uses natural language, not technical jargon
5. If data is missing or queries failed, acknowledge this gracefully

Do NOT include SQL queries or technical details in your response unless specifically asked.
Format your response with clear paragraphs. Use bullet points for lists of items.

Response:"""

        try:
            response = self.claude.messages.create(
                model=self.settings.CLAUDE_MODEL,
                max_tokens=self.settings.CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Error generating interpretation: {e}")
            return f"I was able to retrieve the data but encountered an error generating the interpretation: {str(e)}"

    def _format_data_as_text(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
    ) -> str:
        """Format data as a simple text table for Claude context.

        Args:
            data: List of row dictionaries
            columns: Column names

        Returns:
            Formatted text table
        """
        if not data:
            return "No data"

        if not columns:
            columns = list(data[0].keys()) if data else []

        # Build simple table
        lines = []
        lines.append(" | ".join(columns))
        lines.append("-" * len(lines[0]))

        for row in data:
            values = []
            for col in columns:
                val = row.get(col, "")
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                elif val is None:
                    val = "N/A"
                else:
                    val = str(val)
                values.append(val)
            lines.append(" | ".join(values))

        return "\n".join(lines)

    def _merge_data_results(
        self,
        genie_results: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Merge data from all sub-question results.

        Returns the data from the result with the most rows.

        Args:
            genie_results: Results from all sub-questions

        Returns:
            Data from the result with the most rows
        """
        best_data = None
        best_count = 0
        for result in genie_results:
            data = result.get("data")
            if data and len(data) > best_count:
                best_data = data
                best_count = len(data)
        return best_data

    def _get_all_columns(
        self,
        genie_results: List[Dict[str, Any]],
    ) -> Optional[List[str]]:
        """Get columns from the result with the most data.

        Args:
            genie_results: Results from all sub-questions

        Returns:
            Column names from result with most data
        """
        best_columns = None
        best_count = 0
        for result in genie_results:
            data = result.get("data")
            columns = result.get("columns")
            if data and columns and len(data) > best_count:
                best_columns = columns
                best_count = len(data)
        return best_columns

    def _get_all_data_sets(
        self,
        genie_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Get all data sets from sub-question results.

        Args:
            genie_results: Results from all sub-questions

        Returns:
            List of data sets with their sub-questions and columns
        """
        data_sets = []
        for result in genie_results:
            data = result.get("data")
            if data:
                data_sets.append({
                    "sub_question": result.get("sub_question", ""),
                    "columns": result.get("columns", []),
                    "data": data,
                    "row_count": len(data),
                })
        return data_sets
