"""Claude AI service for text-to-SQL generation (replaces Databricks Genie)."""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from anthropic import Anthropic

from app.config import get_settings
from app.security import validate_query, SQLValidationError

logger = logging.getLogger(__name__)
settings = get_settings()


# PostgreSQL schema context for Claude (from SUPABASE_SCHEMA.md)
SCHEMA_CONTEXT = """
# PostgreSQL Schema for Senture Orbit Pharmaceutical BI

## Dimension Tables

### dim.product
- product_id VARCHAR(64) PRIMARY KEY - SHA256 hash of product_code
- product_code VARCHAR(50) - Product code (e.g., '1350001')
- product_name VARCHAR(200) - Product name (e.g., 'Disprin 100s')
- brand VARCHAR(100) - Brand name (e.g., 'Disprin')
- category VARCHAR(50) - Therapeutic category (Pain, Cardio, Gastro, etc.)
- manufacturer_code VARCHAR(50)
- nappi_clean VARCHAR(20) - SA pharmaceutical ID

Sample: 10 products in categories: Pain, Cardio, Gastro, Gout, etc.

### dim.customer
- customer_id VARCHAR(64) PRIMARY KEY - SHA256 hash of customer_key
- customer_name VARCHAR(200) - Customer/pharmacy name
- customer_type VARCHAR(50) - PHARMACY, WHOLESALER, HCP
- customer_group VARCHAR(100) - Private, Public, Chain
- region VARCHAR(100) - Geographic region (Johannesburg, Cape Town, Durban, etc.)
- province VARCHAR(100)
- town VARCHAR(100)
- speciality VARCHAR(100) - For HCP customers

Sample: 5 customers (mostly wholesalers)

### dim.rep
- rep_id VARCHAR(64) PRIMARY KEY - SHA256 hash of rep_code
- rep_code VARCHAR(50) - Sales rep code
- rep_name VARCHAR(200) - Sales rep name
- territory VARCHAR(100) - Assigned territory
- region VARCHAR(100) - Regional assignment
- is_active BOOLEAN

Sample: 5 active sales reps

### dim.date
- date_key DATE PRIMARY KEY - Date (YYYY-MM-DD)
- yyyymm VARCHAR(7) - Year-month (YYYY-MM)
- year INTEGER, month INTEGER, quarter INTEGER
- month_name VARCHAR(20) - January, February, etc.
- is_business_day BOOLEAN - Weekday and not holiday
- is_holiday BOOLEAN
- holiday_name VARCHAR(100) - SA public holidays

Range: 2023-01-01 to 2027-12-31 (1,825 days)

## Fact Tables

### fact.secondary_sales_daily
Daily secondary sales (sell-out to end consumers)
- date_key DATE - FK to dim.date
- product_id VARCHAR(64) - FK to dim.product
- customer_id VARCHAR(64) - FK to dim.customer
- delivered_qty NUMERIC(18,2) - Units sold
- secondary_value NUMERIC(18,2) - Sales value in ZAR
- PRIMARY KEY (date_key, product_id, customer_id)

Sample: ~6,500 transactions (2024-2025)

### fact.primary_sales_monthly
Monthly primary sales (sell-in to pharmacies/wholesalers)
- yyyymm VARCHAR(7) - Year-month (YYYY-MM)
- product_id VARCHAR(64) - FK to dim.product
- customer_id VARCHAR(64) - FK to dim.customer
- primary_value NUMERIC(18,2) - Net sales value (ZAR)
- qty_moved NUMERIC(18,2) - Quantity sold
- PRIMARY KEY (yyyymm, product_id, customer_id)

Sample: ~600 records

### fact.stock_latest
Latest stock levels snapshot
- snapshot_date DATE - FK to dim.date
- product_id VARCHAR(64) - FK to dim.product
- customer_id VARCHAR(64) - FK to dim.customer
- soh NUMERIC(18,2) - Stock on hand
- min_qty NUMERIC(18,2) - Minimum threshold
- max_qty NUMERIC(18,2) - Maximum threshold
- avg_sales NUMERIC(18,2) - Average daily sales rate
- PRIMARY KEY (snapshot_date, product_id, customer_id)

Sample: ~50 records

### fact.rep_calls_daily
Daily sales rep calls/visits
- date_key DATE - FK to dim.date
- rep_id VARCHAR(64) - FK to dim.rep
- customer_id VARCHAR(64) - FK to dim.customer
- call_type VARCHAR(50) - PLANNED, ADHOC, FOLLOW_UP
- visited VARCHAR(1) - 'Y' or 'N'
- new_order NUMERIC(18,2) - New order value
- written_value NUMERIC(18,2) - Written/recorded value
- PRIMARY KEY (date_key, rep_id, customer_id)

### fact.rep_activity_monthly
Monthly aggregated rep performance metrics
- yyyymm VARCHAR(7)
- rep_id VARCHAR(64) - FK to dim.rep
- total_calls INTEGER
- unique_calls INTEGER - Unique customers called
- productive_calls INTEGER - Calls with orders
- coverage_percent NUMERIC(5,2) - % of territory covered
- strike_rate NUMERIC(5,2) - Orders / Calls (%)
- avg_calls_per_day NUMERIC(5,2)
- customers_seen INTEGER
- new_orders INTEGER
- written_value NUMERIC(18,2)
- PRIMARY KEY (rep_id, yyyymm)

### fact.targets_2025
2025 sales targets by product
- product_id VARCHAR(64) - FK to dim.product
- target_type VARCHAR(20) - 'PRIMARY' or 'SECONDARY'
- target_volume_2025 NUMERIC(18,2)
- target_value_2025 NUMERIC(18,2)
- PRIMARY KEY (product_id, target_type)

## Aggregated Views

### agg.kpi_dashboard (Materialized View)
Pre-computed KPI dashboard with stock opportunities
- product_code, product_name, brand
- customer_name, customer_group, region
- soh - Stock on hand
- avg_daily_units - Average daily sales
- dsoh_days - Days stock on hand
- ideal_stock_45d_units - Target stock for 45 days
- opportunity_units - Stock gap in units
- opportunity_value - Stock gap in ZAR

### agg.vw_product_performance
Product performance with actuals vs targets
- product_code, product_name, brand, category
- primary_qty_2025, primary_value_2025
- primary_target_volume_2025, primary_target_value_2025
- primary_attainment_pct
- secondary_qty_2025, secondary_value_2025
- secondary_target_volume_2025, secondary_target_value_2025
- secondary_attainment_pct
- soh_latest, avg_daily_sales

### agg.vw_rep_performance
Sales rep performance metrics (latest month)
- rep_id, rep_code, rep_name, territory, region
- yyyymm, total_calls, unique_calls, productive_calls
- coverage_percent, strike_rate
- workable_days, days_worked, work_rate_pct
- avg_calls_per_day, customers_seen
- new_orders, written_value

## Common Query Patterns

### Sales Analysis
- Always JOIN fact tables with dim tables using foreign keys
- Use date_key for daily facts, yyyymm for monthly facts
- Filter dates with: WHERE date_key >= CURRENT_DATE - INTERVAL '30 days'
- For year-to-date: WHERE date_key >= DATE_TRUNC('year', CURRENT_DATE)

### Aggregations
- Use SUM() for values and quantities
- Use COUNT(*) for counting records
- Use AVG() for averages
- Always GROUP BY dimension columns when aggregating

### Stock Analysis
- Use agg.kpi_dashboard for pre-computed stock opportunities
- Filter by: WHERE dsoh_days < 45 AND opportunity_value > 0
- Order by: ORDER BY opportunity_value DESC

### Rep Performance
- Use agg.vw_rep_performance for current month metrics
- Use fact.rep_activity_monthly for historical trends
- Join with dim.rep for rep details
"""


SQL_GENERATION_PROMPT = """You are a SQL expert for a pharmaceutical BI system using PostgreSQL.

# Database Schema
{schema_context}

# Similar Past Queries (for reference)
{similar_queries}

# User Question
{user_question}

Generate a PostgreSQL SELECT query to answer this question.

Requirements:
- Use ONLY SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
- Reference tables as schema.table (e.g., dim.product, fact.secondary_sales_daily)
- Use proper JOINs with foreign keys (product_id, customer_id, rep_id, date_key)
- Include appropriate WHERE clauses for filtering
- Use LIMIT clause if the question implies "top N" results
- For date filtering:
  - Daily facts: WHERE date_key >= CURRENT_DATE - INTERVAL '30 days'
  - Monthly facts: WHERE yyyymm >= '2025-01'
- Round numeric results: ROUND(value::NUMERIC, 2)
- Handle NULL values with COALESCE() when appropriate
- Use meaningful column aliases
- For percentage calculations: ROUND((numerator / NULLIF(denominator, 0) * 100)::NUMERIC, 1)

Return ONLY the SQL query without explanation or markdown formatting.
"""


class ClaudeService:
    """
    Claude AI service for text-to-SQL generation.

    This service replaces Databricks Genie and provides:
    - Direct Claude-to-SQL generation
    - Query complexity classification (route to Haiku or Sonnet)
    - RAG integration (retrieve similar past queries)
    - SQL safety validation
    """

    def __init__(self, qdrant_service=None):
        """
        Initialize Claude service.

        Args:
            qdrant_service: Optional QdrantService for RAG retrieval
        """
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.qdrant = qdrant_service
        self.schema_context = SCHEMA_CONTEXT

    async def classify_query_complexity(self, question: str) -> Tuple[str, float]:
        """
        Classify query as 'simple' or 'complex'.

        Simple queries:
        - Single table queries
        - Basic aggregations (SUM, COUNT, AVG)
        - Simple filters
        - Pre-computed views (agg.*)

        Complex queries:
        - Multi-table JOINs (3+ tables)
        - Nested subqueries
        - Complex date logic
        - Window functions
        - Year-over-year comparisons

        Args:
            question: Natural language question

        Returns:
            Tuple of (complexity_level, confidence_score)
        """
        classification_prompt = f"""
Classify this SQL query complexity as 'simple' or 'complex'.

Question: {question}

Simple queries:
- Single table or view queries
- Basic aggregations (SUM, COUNT, AVG, MAX, MIN)
- Simple WHERE filters
- Direct lookups
- Pre-computed views (agg.kpi_dashboard, agg.vw_*)

Complex queries:
- Multiple table JOINs (3+ tables)
- Nested subqueries or CTEs
- Window functions (ROW_NUMBER, RANK, LAG, LEAD)
- Complex date calculations
- Year-over-year or period comparisons
- Statistical calculations

Respond with ONLY: 'simple' or 'complex'
"""

        try:
            message = self.client.messages.create(
                model=settings.CLAUDE_HAIKU_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": classification_prompt}]
            )

            complexity = message.content[0].text.strip().lower()

            # Default to 'complex' if unclear
            if complexity not in ['simple', 'complex']:
                logger.warning(
                    f"Unexpected complexity classification: {complexity}, "
                    f"defaulting to 'complex'"
                )
                complexity = 'complex'

            logger.info(f"Query classified as: {complexity}")
            return complexity, 1.0

        except Exception as e:
            logger.error(f"Error classifying query complexity: {e}")
            # Default to complex on error (safer)
            return 'complex', 0.5

    async def retrieve_similar_queries(
        self,
        question: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar past queries from Qdrant (RAG).

        Args:
            question: User's natural language question
            top_k: Number of similar queries to retrieve

        Returns:
            List of similar queries with their SQL and results
        """
        if self.qdrant is None:
            logger.warning("Qdrant service not initialized, skipping RAG retrieval")
            return []

        try:
            similar_queries = await self.qdrant.search_similar_queries(
                question, top_k
            )
            logger.info(f"Retrieved {len(similar_queries)} similar queries via RAG")
            return similar_queries

        except Exception as e:
            logger.error(f"Error retrieving similar queries: {e}")
            return []

    def validate_sql_safety(self, sql: str) -> bool:
        """
        Validate that SQL is safe (SELECT-only, no dangerous operations).

        Uses the centralized SQLValidator for comprehensive security checks.

        Args:
            sql: Generated SQL query

        Returns:
            True if safe, raises SQLValidationError if dangerous

        Raises:
            SQLValidationError: If SQL contains dangerous operations
        """
        try:
            validate_query(sql, allow_multiple_statements=False)
            logger.debug("SQL safety validation passed")
            return True
        except SQLValidationError as e:
            logger.error(f"SQL validation failed: {e}")
            raise ValueError(str(e)) from e

    async def generate_sql(
        self,
        question: str,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language question.

        Args:
            question: Natural language question
            use_rag: Whether to use RAG for similar queries

        Returns:
            Dictionary with:
                - sql: Generated SQL query
                - model: Model used (haiku/sonnet)
                - complexity: Query complexity (simple/complex)
                - similar_queries: Retrieved similar queries (if RAG enabled)
        """
        # Step 1: Classify complexity
        complexity, confidence = await self.classify_query_complexity(question)

        # Step 2: Retrieve similar queries (RAG)
        similar_queries = []
        if use_rag:
            similar_queries = await self.retrieve_similar_queries(
                question, top_k=settings.RAG_TOP_K
            )

        # Step 3: Build prompt with schema + examples
        similar_queries_text = ""
        if similar_queries:
            similar_queries_text = "\n\n".join([
                f"Example {i+1}:\n"
                f"Question: {q['question']}\n"
                f"SQL: {q['sql']}"
                for i, q in enumerate(similar_queries)
            ])
        else:
            similar_queries_text = "No similar past queries available."

        prompt = SQL_GENERATION_PROMPT.format(
            schema_context=self.schema_context,
            similar_queries=similar_queries_text,
            user_question=question
        )

        # Step 4: Route to appropriate model based on complexity
        if complexity == 'simple':
            model = settings.CLAUDE_HAIKU_MODEL
            logger.info(f"Using Haiku for simple query")
        else:
            model = settings.CLAUDE_SONNET_MODEL
            logger.info(f"Using Sonnet for complex query")

        # Step 5: Generate SQL
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            sql = message.content[0].text.strip()

            # Remove markdown code blocks if present
            sql = re.sub(r'^```sql\n', '', sql)
            sql = re.sub(r'^```\n', '', sql)
            sql = re.sub(r'\n```$', '', sql)
            sql = sql.strip()

            # Step 6: Validate SQL safety
            self.validate_sql_safety(sql)

            logger.info(f"SQL generated successfully using {model}")

            return {
                "sql": sql,
                "model": model,
                "complexity": complexity,
                "similar_queries": similar_queries,
            }

        except ValueError as e:
            # SQL safety validation failed
            logger.error(f"SQL safety validation failed: {e}")
            raise

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            raise

    async def generate_answer_from_results(
        self,
        question: str,
        sql: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Generate natural language answer from SQL results.

        Args:
            question: Original question
            sql: Executed SQL query
            results: Query results

        Returns:
            Natural language answer
        """
        if not results:
            return "No results found for this query."

        # Limit results to first 10 rows for answer generation
        results_sample = results[:10]

        answer_prompt = f"""
Based on the SQL query results, provide a concise answer to the user's question.

Question: {question}

SQL Query: {sql}

Results (first {len(results_sample)} of {len(results)} rows):
{results_sample}

Provide a clear, concise answer in 2-3 sentences. Include key numbers and insights.
If there are many results, summarize the top findings.
"""

        try:
            message = self.client.messages.create(
                model=settings.CLAUDE_HAIKU_MODEL,  # Use Haiku for answer formatting
                max_tokens=500,
                messages=[{"role": "user", "content": answer_prompt}]
            )

            answer = message.content[0].text.strip()
            logger.info("Answer generated from results")
            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            # Fallback to simple summary
            return f"Found {len(results)} results. Query executed successfully."
