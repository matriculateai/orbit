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

# Silver layer schema context for Claude
SCHEMA_CONTEXT = """
You have access to a pharmaceutical commercial intelligence database (Zydus) with the following silver layer tables.
All tables are in the `zydus.silver` schema.

## Sales Data

### zydus.silver.primary_sales
Primary sales transactions (sell-in from manufacturer to distributor/pharmacy).
| Column | Type | Description |
|--------|------|-------------|
| trans_date | date | Transaction date |
| month_label | string | Month label |
| trans_type | string | Transaction type |
| trans_no | string | Transaction number |
| bill_to_acc | string | Bill-to account code |
| bill_to_name | string | Bill-to customer name |
| ship_to_acc | string | Ship-to account code |
| ship_to_name | string | Ship-to customer name |
| sector | string | Business sector |
| universe | string | Universe/segment |
| dc_source | string | Distribution center source |
| po_number | string | Purchase order number |
| encode | string | Product encode |
| upd_code | string | UPD code |
| manufacturer_code | string | Manufacturer code |
| product_description | string | Product description/name |
| batch_no | string | Batch number |
| expiry_date | date | Batch expiry date |
| batch_qty | double | Batch quantity |
| qty_ordered | double | Quantity ordered |

### zydus.silver.secondary_sales
Secondary sales transactions (sell-out from pharmacy to end consumer).
| Column | Type | Description |
|--------|------|-------------|
| transaction_number | string | Transaction number |
| delivered_qty | double | Delivered quantity |
| bonus_qty | double | Bonus quantity |
| price | double | Price per unit |
| transaction_date | date | Transaction date |
| order_number | string | Order number |
| transaction_type | string | Transaction type |
| invoice_number | string | Invoice number |
| customer_name | string | Customer/pharmacy name |
| product | string | Product name |
| ssd_sra | string | SSD SRA code |
| sra_code | string | SRA code |
| grade | string | Customer grade (A, B, C, etc.) |
| supplier | string | Supplier name |
| brand | string | Brand name |
| product_group | string | Product group |
| ssd_customer_group | string | Customer group |
| country | string | Country |
| province | string | Province |
| region | string | Region (e.g., "Gauteng", "Western Cape") |

## Targets

### zydus.silver.primary_sales_targets
Monthly primary sales targets for 2025 by product.
| Column | Type | Description |
|--------|------|-------------|
| mnf_code | string | Manufacturer code |
| product_code | string | Product code |
| product_name | string | Product name |
| brand | string | Brand name |
| business | string | Business unit |
| revenue_split | double | Revenue split percentage |
| base_business_split | double | Base business split |
| category | string | Product category |
| salesvol_jan_25 | double | January 2025 target volume |
| salesvol_feb_25 | double | February 2025 target volume |
| salesvol_mar_25 | double | March 2025 target volume |
| salesvol_apr_25 | double | April 2025 target volume |
| salesvol_may_25 | double | May 2025 target volume |
| salesvol_jun_25 | double | June 2025 target volume |
| salesvol_jul_25 | double | July 2025 target volume |
| salesvol_aug_25 | double | August 2025 target volume |
| salesvol_sep_25 | double | September 2025 target volume |
| salesvol_oct_25 | double | October 2025 target volume |
| salesvol_nov_25 | double | November 2025 target volume |
| salesvol_dec_25 | double | December 2025 target volume |

### zydus.silver.secondary_sales_targets
Monthly secondary sales targets for 2025 by product and customer group.
| Column | Type | Description |
|--------|------|-------------|
| product_code | string | Product code |
| product_name | string | Product name |
| brand | string | Brand name |
| product_group | string | Product group |
| customer_group | string | Customer group |
| target_jan_25 | double | January 2025 target |
| target_feb_25 | double | February 2025 target |
| target_mar_25 | double | March 2025 target |
| target_apr_25 | double | April 2025 target |
| target_may_25 | double | May 2025 target |
| target_jun_25 | double | June 2025 target |
| target_jul_25 | double | July 2025 target |
| target_aug_25 | double | August 2025 target |
| target_sep_25 | double | September 2025 target |
| target_oct_25 | double | October 2025 target |
| target_nov_25 | double | November 2025 target |
| target_dec_25 | double | December 2025 target |
| target_total_25 | double | Total 2025 target |
| loaded_at | timestamp | Data load timestamp |

## Inventory & Stock

### zydus.silver.order_dynamics
Current stock levels and inventory dynamics by product and location.
| Column | Type | Description |
|--------|------|-------------|
| product_name | string | Product name |
| product_code | string | Product code |
| nappi | string | NAPPI code (South African pharmaceutical ID) |
| location | string | Stock location/warehouse |
| soh | double | Stock on hand (current inventory) |
| min_qty | double | Minimum stock quantity threshold |
| max_qty | double | Maximum stock quantity threshold |
| avg_sales | double | Average sales rate |

### zydus.silver.backorders
Backorder data - orders that couldn't be fulfilled.
| Column | Type | Description |
|--------|------|-------------|
| created_date | date | Backorder creation date |
| branch | string | Branch |
| supply_from | string | Supply source |
| client_code | string | Client code |
| category | string | Product category |
| issue_code | string | Issue code |
| process_code | string | Process code |
| order_no | string | Order number |
| warehouse | string | Warehouse |
| manufacture_id | string | Manufacturer ID |
| manufacture_code | string | Manufacturer code |
| sku_id | string | SKU ID |
| sku_name | string | SKU/Product name |
| sku_type | string | SKU type |
| qty | double | Backorder quantity |
| qty_without_ration | double | Quantity without rationing |
| qty_if | double | Quantity if available |
| volume | double | Volume value |
| status | string | Backorder status |
| reason | string | Backorder reason |

## Sales Rep Activity

### zydus.silver.rep_monthly_activity
Monthly aggregated sales rep performance metrics.
| Column | Type | Description |
|--------|------|-------------|
| rep_code | string | Rep code |
| rep_name | string | Rep name |
| sra_code | string | SRA code |
| territory | string | Territory |
| region | string | Region |
| sub_region | string | Sub-region |
| town | string | Town |
| speciality | string | Medical speciality focus |
| cycle | string | Sales cycle |
| month | string | Month name |
| month_number | int | Month number (1-12) |
| year | int | Year |
| total_calls | int | Total calls made |
| unique_calls | int | Unique customer calls |
| productive_calls | int | Productive calls (resulted in activity) |
| coverage_percent | double | Coverage percentage (customers visited / total customers) |
| workable_days | int | Workable days in month |
| days_worked | int | Actual days worked |
| strike_rate | double | Strike rate (orders / calls percentage) |
| avg_calls_per_day | double | Average calls per day |

### zydus.silver.repwize_coverage
Detailed rep call/visit records by customer.
| Column | Type | Description |
|--------|------|-------------|
| rep_code | string | Rep code |
| rep_name | string | Rep name |
| rep_sra | string | Rep SRA code |
| rep_territory | string | Rep territory |
| customer_code | string | Customer code |
| customer_name | string | Customer name |
| speciality | string | Customer speciality |
| grade | string | Customer grade (A, B, C - importance ranking) |
| region | string | Region |
| sub_region | string | Sub-region |
| town | string | Town |
| brick | string | Brick (geographic micro-area) |
| call_date | date | Call/visit date |
| call_type | string | Type of call |
| visited | string | Whether customer was visited (Y/N) |
| calls_in_cycle | int | Calls made in current cycle |
| unique_calls | int | Unique calls |
| appointment | string | Whether appointment was made |
| new_order | double | New order value from this call |
| written_value | double | Written/recorded value |

## Key Business Concepts

- **Primary Sales**: Sell-in from manufacturer (Zydus) to distributors/pharmacies
- **Secondary Sales**: Sell-out from pharmacies to end consumers/patients
- **SOH (Stock on Hand)**: Current inventory level at a location
- **DSOH (Days Stock on Hand)**: SOH / avg_sales = days until stockout
- **Strike Rate**: Percentage of rep calls that result in orders
- **Coverage**: Percentage of target customers visited by reps
- **Backorders**: Orders that couldn't be fulfilled due to stock issues
- **NAPPI Code**: South African pharmaceutical product identifier
- **SRA**: Sales Rep Area code
- **Grade**: Customer importance ranking (A=highest, B, C, etc.)

## Common Query Patterns

1. **Sales Performance**: Join primary_sales or secondary_sales with targets tables
2. **Stock Analysis**: Use order_dynamics for current stock, calculate DSOH as soh/avg_sales
3. **Rep Performance**: Use rep_monthly_activity for aggregates, repwize_coverage for details
4. **Target vs Actual**: Compare sales tables with corresponding targets tables by month
5. **Regional Analysis**: Group by region, province, or sub_region columns
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
1. Be answerable with a single SQL query
2. Prefer tables from `zydus.silver.*` as documented above
3. Be clear and unambiguous

IMPORTANT:
- The database has both `zydus.silver` and `zydus.gold` schemas available
- Prefer the silver schema tables documented above when possible
- Keep questions focused on data that exists in the schema

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
