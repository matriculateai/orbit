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
from app.services.genie_client import GenieClient

logger = logging.getLogger(__name__)

# Gold layer schema context for Claude
SCHEMA_CONTEXT = """
You have access to a pharmaceutical commercial intelligence database (Zydus) with the following GOLD layer tables.
All tables are in the `zydus.gold` schema. This is a star schema with dimension and fact tables.

## DIMENSION TABLES

### zydus.gold.dim_product
Product master dimension with all product attributes.
| Column | Type | Description |
|--------|------|-------------|
| product_id | string | Unique product identifier (hash key) |
| product_code | string | Product code (business key) |
| product_name | string | Product name |
| manufacturer_code | string | Manufacturer code |
| nappi_clean | string | Cleaned NAPPI code (South African pharmaceutical ID) |
| brand | string | Brand name |
| product_group | string | Product group/category |
| category | string | Product category (Pain, Cardio, Gastro, etc.) |

### zydus.gold.dim_customer
Customer master dimension with all customer attributes.
| Column | Type | Description |
|--------|------|-------------|
| customer_id | string | Unique customer identifier (hash key) |
| customer_name | string | Customer display name |
| customer_key | string | Normalized customer key for matching |
| customer_type | string | Customer type (PHARMACY, WHOLESALER, etc.) |
| customer_group | string | Customer group/segment |
| country | string | Country |
| province | string | Province |
| region | string | Region (e.g., "Gauteng", "Western Cape") |
| sub_region | string | Sub-region |
| town | string | Town |
| suburb | string | Suburb |
| speciality | string | Medical speciality (for HCP customers) |

### zydus.gold.dim_rep
Sales representative dimension.
| Column | Type | Description |
|--------|------|-------------|
| rep_id | string | Unique rep identifier (hash key) |
| rep_code | string | Rep code (business key) |
| rep_name | string | Rep name |
| region | string | Rep's region |
| territory | string | Rep's territory |
| sra_code | string | Sales Rep Area code |

### zydus.gold.dim_date
Date dimension for time-based analysis.
| Column | Type | Description |
|--------|------|-------------|
| date_key | date | Date (primary key) |
| year | int | Year (e.g., 2025) |
| month | int | Month number (1-12) |
| yyyymm | string | Year-month string (e.g., "2025-01") |
| month_name | string | Month name (e.g., "January") |
| quarter | int | Quarter (1-4) |

## FACT TABLES

### zydus.gold.fact_primary_sales_monthly
Aggregated primary sales (sell-in) by month, product, and customer.
| Column | Type | Description |
|--------|------|-------------|
| yyyymm | string | Year-month (e.g., "2025-01") |
| product_id | string | FK to dim_product |
| customer_id | string | FK to dim_customer |
| primary_value | double | Total primary sales value (ZAR) |
| qty_moved | double | Total quantity sold |

### zydus.gold.fact_secondary_sales_daily
Daily secondary sales (sell-out) transactions.
| Column | Type | Description |
|--------|------|-------------|
| date_key | date | Transaction date (FK to dim_date) |
| product_id | string | FK to dim_product |
| customer_id | string | FK to dim_customer |
| delivered_qty | double | Quantity delivered |
| secondary_value | double | Sales value (ZAR) |

### zydus.gold.fact_stock_latest
Current stock levels (latest snapshot).
| Column | Type | Description |
|--------|------|-------------|
| snapshot_date | date | Date of stock snapshot |
| product_id | string | FK to dim_product |
| customer_id | string | FK to dim_customer (location) |
| soh | double | Stock on hand (current inventory units) |
| min_qty | double | Minimum stock threshold |
| max_qty | double | Maximum stock threshold |
| avg_sales | double | Average daily sales rate |

### zydus.gold.fact_backorders_monthly
Monthly backorder aggregates.
| Column | Type | Description |
|--------|------|-------------|
| yyyymm | string | Year-month |
| product_id | string | FK to dim_product |
| customer_id | string | FK to dim_customer |
| qty | double | Backorder quantity |
| volume | double | Backorder volume value |

### zydus.gold.fact_rep_calls_daily
Daily sales rep call/visit records.
| Column | Type | Description |
|--------|------|-------------|
| date_key | date | Call date (FK to dim_date) |
| rep_id | string | FK to dim_rep |
| customer_id | string | FK to dim_customer |
| call_type | string | Type of call |
| visited | string | Whether customer was visited (Y/N) |
| new_order | double | New order value from this call |
| written_value | double | Written/recorded value |

### zydus.gold.fact_rep_activity_monthly
Monthly aggregated rep performance metrics.
| Column | Type | Description |
|--------|------|-------------|
| rep_id | string | FK to dim_rep |
| yyyymm | string | Year-month |
| total_calls | int | Total calls made |
| unique_calls | int | Unique customer calls |
| productive_calls | int | Productive calls (resulted in activity) |
| coverage_percent | double | Coverage % (customers visited / total) |
| workable_days | int | Workable days in month |
| days_worked | int | Actual days worked |
| strike_rate | double | Strike rate (orders / calls %) |
| avg_calls_per_day | double | Average calls per day |
| customers_seen | int | Number of customers seen |
| appointments | int | Number of appointments |
| new_orders | int | Number of new orders |
| written_value | double | Total written value |

### zydus.gold.fact_targets_2025
2025 sales targets by product and target type.
| Column | Type | Description |
|--------|------|-------------|
| product_id | string | FK to dim_product |
| product_code | string | Product code |
| target_type | string | Target type (PRIMARY or SECONDARY) |
| target_volume_2025 | double | 2025 volume target |
| target_value_2025 | double | 2025 value target (ZAR) |

## VIEWS (Pre-calculated KPIs)

### zydus.gold.mv_kpi_dashboard
Pre-calculated KPI dashboard with stock opportunities.
| Column | Type | Description |
|--------|------|-------------|
| product_code | string | Product code |
| product_name | string | Product name |
| brand | string | Brand |
| customer_name | string | Customer name |
| customer_group | string | Customer group |
| region | string | Region |
| soh | double | Stock on hand |
| avg_daily_units | double | Average daily sales units |
| dsoh_days | double | Days stock on hand (SOH / avg_daily) |
| ideal_stock_45d_units | double | Ideal stock for 45 days |
| opportunity_units | double | Stock opportunity in units (ideal - SOH) |
| opportunity_value | double | Stock opportunity value (ZAR) |

### zydus.gold.vw_rep_customer_coverage
Detailed rep coverage with derived KPIs.
| Column | Type | Description |
|--------|------|-------------|
| rep_id | string | Rep ID |
| rep_code | string | Rep code |
| rep_name | string | Rep name |
| rep_sra | string | Rep SRA |
| rep_territory | string | Rep territory |
| customer_code | string | Customer code |
| customer_name | string | Customer name |
| speciality | string | Customer speciality |
| grade | string | Customer grade (A, B, C) |
| customer_region | string | Customer region |
| call_date | date | Call date |
| yyyymm | string | Year-month |
| year | int | Year |
| quarter | int | Quarter |
| month | int | Month |
| call_type | string | Call type |
| visited | string | Visited (Y/N) |
| new_order | double | New order value |
| written_value | double | Written value |
| work_rate | double | Work rate (days_worked / workable_days) |
| unique_call_ratio | double | Unique call ratio |
| visit_flag | int | Visit flag (1 if visited) |
| unique_calls_per_day | double | Unique calls per day |

## KEY BUSINESS CONCEPTS & KPI CALCULATIONS

- **Primary Sales**: Sell-in from manufacturer (Zydus) to distributors/pharmacies
- **Secondary Sales**: Sell-out from pharmacies to end consumers/patients
- **SOH (Stock on Hand)**: Current inventory level at a location
- **DSOH (Days Stock on Hand)**: `soh / avg_sales` = days until stockout
- **Ideal Stock**: 45 days of stock = `45 * avg_daily_units`
- **Opportunity Units**: Stock gap = `ideal_stock_45d_units - soh`
- **Opportunity Value**: `opportunity_units * avg_unit_price`
- **Strike Rate**: Percentage of rep calls that result in orders
- **Coverage %**: Percentage of target customers visited by reps
- **Work Rate**: `days_worked / workable_days`

## COMMON QUERY PATTERNS

1. **Sales vs Target**: Join `fact_primary_sales_monthly` or `fact_secondary_sales_daily` with `fact_targets_2025` via `product_id`
2. **Stock Opportunities**: Use `mv_kpi_dashboard` for pre-calculated opportunities, or join `fact_stock_latest` with `dim_product` and `dim_customer`
3. **Rep Performance**: Use `fact_rep_activity_monthly` for aggregates, join with `dim_rep` for rep details
4. **Customer Analysis**: Join fact tables with `dim_customer` for regional/segment breakdowns
5. **Time Analysis**: Join fact tables with `dim_date` for period comparisons

## IMPORTANT NOTES

- Always join fact tables to dimension tables using the `_id` columns (product_id, customer_id, rep_id)
- Use `yyyymm` for monthly aggregations, `date_key` for daily data
- The `mv_kpi_dashboard` view has pre-calculated stock opportunity KPIs - use it for stock analysis
- Target comparisons should filter `fact_targets_2025` by `target_type` (PRIMARY or SECONDARY)
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

    async def close(self) -> None:
        """Close all connections."""
        await self.genie_client.close()

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
        import time
        try:
            start_time = time.time()
            logger.info(f"Processing question for persona '{persona}': {question[:100]}...")

            # Step 1: Decompose question into data sub-questions
            step1_start = time.time()
            sub_questions = await self._generate_sub_questions(question)
            logger.info(f"Generated {len(sub_questions)} sub-questions in {time.time() - step1_start:.1f}s")

            # Step 2: Get SQL from Genie for all sub-questions in parallel
            step2_start = time.time()
            logger.info(f"Sending {len(sub_questions)} sub-questions to Genie in parallel...")

            async def process_sub_question(idx: int, sub_q: str) -> Dict[str, Any]:
                """Process a single sub-question and return formatted result."""
                q_start = time.time()
                logger.info(f"[Q{idx+1}] Starting: {sub_q[:50]}...")
                result = await self._get_genie_response(sub_q, None)  # Each gets its own conversation
                logger.info(f"[Q{idx+1}] Completed in {time.time() - q_start:.1f}s")
                return {
                    "sub_question": sub_q,
                    "sql_query": result.get("sql_query"),
                    "data": result.get("data"),
                    "columns": result.get("columns"),
                    "success": result.get("success", False),
                    "error": result.get("error"),
                    "conversation_id": result.get("conversation_id"),
                }

            # Run all Genie queries in parallel
            genie_results = await asyncio.gather(
                *[process_sub_question(i, q) for i, q in enumerate(sub_questions)]
            )
            genie_results = list(genie_results)

            # Get a conversation ID from any successful result
            for result in genie_results:
                if result.get("conversation_id"):
                    conversation_id = result.get("conversation_id")
                    break

            logger.info(f"Completed {len(genie_results)} parallel Genie queries in {time.time() - step2_start:.1f}s")

            # Step 3: Generate interpretation with Claude
            step3_start = time.time()
            interpretation = await self._generate_interpretation(
                original_question=question,
                sub_questions_results=genie_results,
                persona=persona,
            )
            logger.info(f"Generated interpretation in {time.time() - step3_start:.1f}s")
            logger.info(f"Total processing time: {time.time() - start_time:.1f}s")

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
1. Be answerable with a single SQL query against the `zydus.gold` schema
2. Use the dimension and fact tables documented above
3. Be clear and unambiguous

IMPORTANT:
- ONLY use tables from the `zydus.gold` schema as documented above
- Use dimension tables (dim_*) for lookups and fact tables (fact_*) for metrics
- For stock opportunities, prefer the `mv_kpi_dashboard` view which has pre-calculated KPIs
- Join fact tables to dimension tables using the `_id` columns

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
