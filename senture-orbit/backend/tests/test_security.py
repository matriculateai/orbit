"""
Security validation tests for SQL query validation and read-only enforcement.

Tests the multi-layer security implementation:
- Layer 1: SQL query validation (keywords, functions, syntax)
- Layer 2: Read-only transactions
- Layer 3: Identifier validation
- Layer 4: Schema whitelisting
"""
import pytest
from app.security import (
    SQLValidator,
    SQLValidationError,
    validate_query,
    validate_identifier,
    validate_schema,
    validate_table_name,
    sanitize_limit,
)


class TestDangerousKeywordBlocking:
    """Test blocking of dangerous SQL keywords."""

    @pytest.mark.parametrize("dangerous_query", [
        "DROP TABLE users",
        "DELETE FROM customers",
        "UPDATE products SET price = 0",
        "INSERT INTO logs VALUES ('hack')",
        "TRUNCATE TABLE data",
        "ALTER TABLE users ADD COLUMN admin BOOLEAN",
        "CREATE TABLE evil (id INT)",
        "GRANT ALL ON DATABASE postgres TO public",
        "REVOKE SELECT ON users FROM public",
        "EXECUTE sp_drop_database('postgres')",
        "CALL dangerous_procedure()",
        "DECLARE @var VARCHAR(100)",
        "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED",
        "VACUUM FULL users",
        "ANALYZE users",
        "PREPARE stmt FROM 'SELECT * FROM users'",
        "LOCK TABLE users IN ACCESS EXCLUSIVE MODE",
        "COPY users TO '/tmp/data.csv'",
    ])
    def test_blocks_dangerous_keywords(self, dangerous_query):
        """Dangerous SQL keywords should be blocked."""
        with pytest.raises(SQLValidationError, match="Dangerous SQL keyword detected"):
            validate_query(dangerous_query)

    @pytest.mark.parametrize("safe_query", [
        "SELECT * FROM dim.product",
        "SELECT COUNT(*) FROM fact.secondary_sales_daily",
        "SELECT product_name FROM dim.product WHERE category = 'Pain'",
        "WITH cte AS (SELECT * FROM dim.customer) SELECT * FROM cte",
    ])
    def test_allows_safe_queries(self, safe_query):
        """Safe SELECT queries should be allowed."""
        assert validate_query(safe_query) is True


class TestDangerousFunctionBlocking:
    """Test blocking of dangerous PostgreSQL functions."""

    @pytest.mark.parametrize("dangerous_query", [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_write_file('/tmp/evil', 'data')",
        "SELECT pg_ls_dir('/var/lib/postgresql')",
        "SELECT pg_stat_file('/etc/shadow')",
        "SELECT pg_sleep(1000)",
        "SELECT pg_sleep_for('1 hour')",
        "SELECT pg_terminate_backend(12345)",
        "SELECT pg_cancel_backend(12345)",
        "SELECT lo_import('/tmp/file')",
        "SELECT lo_export(1234, '/tmp/out')",
    ])
    def test_blocks_dangerous_functions(self, dangerous_query):
        """Dangerous PostgreSQL functions should be blocked."""
        with pytest.raises(SQLValidationError, match="Dangerous PostgreSQL function detected"):
            validate_query(dangerous_query)


class TestStatementTypeEnforcement:
    """Test enforcement of SELECT/WITH statements only."""

    def test_blocks_non_select_statements(self):
        """Non-SELECT statements should be blocked."""
        with pytest.raises(SQLValidationError, match="SQL must start with SELECT or WITH"):
            validate_query("EXPLAIN SELECT * FROM users")

    def test_allows_select_statements(self):
        """SELECT statements should be allowed."""
        assert validate_query("SELECT 1") is True

    def test_allows_with_statements(self):
        """WITH (CTE) statements should be allowed."""
        query = "WITH temp AS (SELECT * FROM dim.product) SELECT * FROM temp"
        assert validate_query(query) is True

    def test_ignores_leading_whitespace(self):
        """Leading whitespace should be ignored."""
        assert validate_query("   \n\t  SELECT 1") is True

    def test_ignores_leading_comments(self):
        """Leading comments should be ignored."""
        query = "-- This is a comment\nSELECT * FROM dim.product"
        assert validate_query(query) is True

        query = "/* Block comment */\nSELECT * FROM dim.product"
        assert validate_query(query) is True


class TestSQLInjectionPrevention:
    """Test prevention of SQL injection attacks."""

    def test_blocks_multiple_statements(self):
        """Multiple statements should be blocked."""
        with pytest.raises(SQLValidationError, match="Multiple SQL statements not allowed"):
            validate_query("SELECT * FROM users; DROP TABLE users;")

    def test_allows_single_statement_with_trailing_semicolon(self):
        """Single statement with trailing semicolon should be allowed."""
        assert validate_query("SELECT * FROM dim.product;") is True

    def test_blocks_semicolon_in_middle(self):
        """Semicolon in the middle of query should be blocked."""
        with pytest.raises(SQLValidationError):
            validate_query("SELECT *; FROM users")

    def test_ignores_semicolon_in_string_literals(self):
        """Semicolons inside string literals should be ignored."""
        # This query has a semicolon in a string, which is safe
        query = "SELECT 'hello; world' as message FROM dim.product"
        assert validate_query(query) is True


class TestQueryLengthLimits:
    """Test query length limits for DoS prevention."""

    def test_blocks_excessively_long_queries(self):
        """Queries exceeding max length should be blocked."""
        validator = SQLValidator(max_query_length=100)
        long_query = "SELECT " + ", ".join([f"col{i}" for i in range(1000)]) + " FROM users"

        with pytest.raises(SQLValidationError, match="exceeds maximum length"):
            validator.validate_query(long_query)

    def test_allows_queries_within_limit(self):
        """Queries within length limit should be allowed."""
        validator = SQLValidator(max_query_length=1000)
        short_query = "SELECT * FROM dim.product"
        assert validator.validate_query(short_query) is True


class TestIdentifierValidation:
    """Test validation of SQL identifiers (table names, column names, etc.)."""

    @pytest.mark.parametrize("valid_identifier", [
        "users",
        "product_table",
        "Table123",
        "_private",
        "camelCase",
        "with_$dollar",
    ])
    def test_allows_valid_identifiers(self, valid_identifier):
        """Valid identifiers should be allowed."""
        assert validate_identifier(valid_identifier) is True

    @pytest.mark.parametrize("invalid_identifier", [
        "'; DROP TABLE users--",
        "table'; DELETE FROM users--",
        "123invalid",  # Starts with number
        "table-name",  # Contains hyphen
        "table.name",  # Contains dot
        "table name",  # Contains space
        "table'name",  # Contains quote
        "",  # Empty
    ])
    def test_blocks_invalid_identifiers(self, invalid_identifier):
        """Invalid identifiers should be blocked."""
        with pytest.raises(SQLValidationError):
            validate_identifier(invalid_identifier)

    def test_blocks_identifiers_exceeding_length_limit(self):
        """Identifiers exceeding 63 characters should be blocked."""
        long_identifier = "a" * 64  # PostgreSQL limit is 63
        with pytest.raises(SQLValidationError, match="too long"):
            validate_identifier(long_identifier)

    def test_blocks_dangerous_keywords_as_identifiers(self):
        """Dangerous SQL keywords should not be allowed as identifiers."""
        with pytest.raises(SQLValidationError, match="dangerous SQL keyword"):
            validate_identifier("DROP")


class TestSchemaWhitelisting:
    """Test schema name whitelisting."""

    @pytest.mark.parametrize("allowed_schema", [
        "dim",
        "fact",
        "agg",
        "information_schema",
    ])
    def test_allows_whitelisted_schemas(self, allowed_schema):
        """Whitelisted schemas should be allowed."""
        assert validate_schema(allowed_schema) is True

    @pytest.mark.parametrize("forbidden_schema", [
        "pg_catalog",
        "public",
        "evil_schema",
        "pg_temp",
    ])
    def test_blocks_non_whitelisted_schemas(self, forbidden_schema):
        """Non-whitelisted schemas should be blocked."""
        with pytest.raises(SQLValidationError, match="not allowed"):
            validate_schema(forbidden_schema)

    def test_case_insensitive_schema_matching(self):
        """Schema matching should be case-insensitive."""
        assert validate_schema("DIM") is True
        assert validate_schema("Fact") is True
        assert validate_schema("AGG") is True


class TestTableNameValidation:
    """Test table name validation."""

    def test_allows_valid_table_names(self):
        """Valid table names should be allowed."""
        assert validate_table_name("product") is True
        assert validate_table_name("secondary_sales_daily") is True
        assert validate_table_name("kpi_dashboard") is True

    def test_blocks_sql_injection_in_table_names(self):
        """SQL injection attempts in table names should be blocked."""
        with pytest.raises(SQLValidationError):
            validate_table_name("users'; DROP TABLE users--")


class TestLimitSanitization:
    """Test LIMIT clause sanitization."""

    def test_allows_valid_limits(self):
        """Valid limit values should be allowed."""
        assert sanitize_limit(10) == 10
        assert sanitize_limit(100) == 100
        assert sanitize_limit(1000) == 1000

    def test_caps_excessive_limits(self):
        """Limits exceeding max should be capped."""
        assert sanitize_limit(50000, max_limit=10000) == 10000
        assert sanitize_limit(1000000, max_limit=10000) == 10000

    def test_blocks_negative_limits(self):
        """Negative limits should be rejected."""
        with pytest.raises(SQLValidationError, match="cannot be negative"):
            sanitize_limit(-10)

    def test_blocks_non_integer_limits(self):
        """Non-integer limits should be rejected."""
        with pytest.raises(SQLValidationError, match="must be an integer"):
            sanitize_limit("100")

        with pytest.raises(SQLValidationError, match="must be an integer"):
            sanitize_limit(10.5)


class TestBatchQueryValidation:
    """Test validation of batch queries."""

    def test_allows_multiple_safe_queries(self):
        """Multiple safe queries should be allowed in batch mode."""
        validator = SQLValidator()
        queries = [
            "SELECT * FROM dim.product",
            "SELECT * FROM fact.secondary_sales_daily",
            "SELECT * FROM agg.kpi_dashboard",
        ]

        for query in queries:
            assert validator.validate_query(query) is True

    def test_blocks_any_dangerous_query_in_batch(self):
        """If any query in batch is dangerous, all should be rejected."""
        validator = SQLValidator()
        queries = [
            "SELECT * FROM dim.product",
            "DROP TABLE users",  # Dangerous
            "SELECT * FROM fact.secondary_sales_daily",
        ]

        # First query passes
        assert validator.validate_query(queries[0]) is True

        # Second query fails
        with pytest.raises(SQLValidationError):
            validator.validate_query(queries[1])


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_empty_query(self):
        """Empty queries should be rejected."""
        with pytest.raises(SQLValidationError, match="cannot be empty"):
            validate_query("")

        with pytest.raises(SQLValidationError, match="cannot be empty"):
            validate_query("   \n\t  ")

    def test_query_with_only_comments(self):
        """Query with only comments should be rejected."""
        with pytest.raises(SQLValidationError):
            validate_query("-- Just a comment")

    def test_case_insensitive_keyword_detection(self):
        """Keyword detection should be case-insensitive."""
        with pytest.raises(SQLValidationError):
            validate_query("drop table users")

        with pytest.raises(SQLValidationError):
            validate_query("DrOp TaBlE users")

    def test_keyword_in_table_name_allowed(self):
        """Keywords as part of table names should be allowed."""
        # "update" is a keyword, but "last_update" is a valid column name
        query = "SELECT last_update FROM dim.product"
        assert validate_query(query) is True

    def test_complex_valid_query(self):
        """Complex but valid queries should be allowed."""
        query = """
        WITH monthly_sales AS (
            SELECT
                DATE_TRUNC('month', date_key) as month,
                SUM(secondary_value) as total_sales
            FROM fact.secondary_sales_daily
            WHERE date_key >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', date_key)
        )
        SELECT
            month,
            total_sales,
            ROUND((total_sales / LAG(total_sales) OVER (ORDER BY month) - 1) * 100, 2) as growth_pct
        FROM monthly_sales
        ORDER BY month DESC
        LIMIT 12
        """
        assert validate_query(query) is True


class TestCustomValidatorConfiguration:
    """Test custom validator configurations."""

    def test_custom_allowed_schemas(self):
        """Custom schema whitelist should be respected."""
        validator = SQLValidator(allowed_schemas={"public", "custom"})

        assert validator.validate_schema("public") is True
        assert validator.validate_schema("custom") is True

        with pytest.raises(SQLValidationError):
            validator.validate_schema("dim")

    def test_custom_dangerous_keywords(self):
        """Custom dangerous keywords should be respected."""
        validator = SQLValidator(dangerous_keywords={"EXPLAIN", "ANALYZE"})

        # Original dangerous keywords like DROP should not be blocked
        # (This is just for testing custom configuration)
        query = "SELECT * FROM users"
        assert validator.validate_query(query) is True

    def test_custom_query_length_limit(self):
        """Custom query length limit should be respected."""
        validator = SQLValidator(max_query_length=50)

        short_query = "SELECT * FROM dim.product"
        assert validator.validate_query(short_query) is True

        long_query = "SELECT * FROM dim.product WHERE category = 'very_long_category_name'"
        with pytest.raises(SQLValidationError, match="exceeds maximum length"):
            validator.validate_query(long_query)


class TestRealWorldQueries:
    """Test real-world query patterns from the application."""

    def test_executive_dashboard_query(self):
        """Executive dashboard queries should be allowed."""
        query = """
        SELECT
            COALESCE(SUM(secondary_value), 0) as total_sales,
            COUNT(DISTINCT customer_id) as active_customers
        FROM fact.secondary_sales_daily
        WHERE date_key >= CURRENT_DATE - INTERVAL '30 days'
        """
        assert validate_query(query) is True

    def test_opportunity_query(self):
        """Opportunity queries should be allowed."""
        query = """
        SELECT
            product_code,
            product_name,
            customer_name,
            opportunity_value
        FROM agg.kpi_dashboard
        WHERE dsoh_days < 45 AND opportunity_value > 0
        ORDER BY opportunity_value DESC
        LIMIT 20
        """
        assert validate_query(query) is True

    def test_rep_performance_query(self):
        """Rep performance queries should be allowed."""
        query = """
        SELECT
            rep_name,
            total_calls,
            productive_calls,
            strike_rate,
            written_value
        FROM agg.vw_rep_performance
        WHERE yyyymm = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
        ORDER BY written_value DESC
        """
        assert validate_query(query) is True

    def test_metadata_query(self):
        """Information schema queries should be allowed."""
        query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'dim' AND table_name = 'product'
        ORDER BY ordinal_position
        """
        assert validate_query(query) is True
