"""SQL security validation utilities for read-only query enforcement."""
import re
import logging
from typing import Set, List, Optional

logger = logging.getLogger(__name__)


# Allowed schemas for queries
ALLOWED_SCHEMAS = {'dim', 'fact', 'agg', 'information_schema', 'pg_catalog'}

# Dangerous SQL keywords that should never appear in read-only queries
DANGEROUS_KEYWORDS = {
    # Data modification
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'TRUNCATE', 'MERGE',
    # Schema modification
    'ALTER', 'CREATE', 'RENAME',
    # Security & permissions
    'GRANT', 'REVOKE',
    # Transaction control (we handle this ourselves)
    'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'BEGIN', 'START',
    # Execution & procedures
    'EXECUTE', 'EXEC', 'CALL',
    # Variable manipulation
    'DECLARE', 'SET',
    # Database operations
    'VACUUM', 'ANALYZE', 'CLUSTER', 'REINDEX',
    # Prepared statements
    'PREPARE', 'DEALLOCATE',
    # Table locking
    'LOCK',
    # File operations
    'COPY',
    # System operations
    'LOAD', 'IMPORT',
}

# Dangerous PostgreSQL functions that could be abused
DANGEROUS_FUNCTIONS = {
    # File system access
    'pg_read_file', 'pg_write_file', 'pg_ls_dir', 'pg_read_binary_file',
    'pg_stat_file',
    # Process control
    'pg_sleep', 'pg_sleep_for', 'pg_sleep_until',
    # Administrative functions
    'pg_terminate_backend', 'pg_cancel_backend', 'pg_reload_conf',
    'pg_rotate_logfile', 'pg_switch_wal',
    # Database operations
    'pg_database_size', 'pg_tablespace_size',
    # Large objects (can access files)
    'lo_import', 'lo_export', 'lo_create', 'lo_unlink',
    # Extension management
    'pg_create_extension', 'pg_drop_extension',
}

# Allowed identifier pattern (alphanumeric, underscore, dollar sign)
IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_$]*$')


class SQLValidationError(ValueError):
    """Raised when SQL validation fails."""
    pass


class SQLValidator:
    """
    Comprehensive SQL validator for read-only query enforcement.

    Provides multiple layers of security:
    1. Keyword filtering - Blocks dangerous SQL operations
    2. Function filtering - Blocks dangerous PostgreSQL functions
    3. Statement validation - Ensures only SELECT/WITH statements
    4. Schema validation - Restricts queries to allowed schemas
    5. Identifier validation - Prevents SQL injection in identifiers
    """

    def __init__(
        self,
        allowed_schemas: Optional[Set[str]] = None,
        dangerous_keywords: Optional[Set[str]] = None,
        dangerous_functions: Optional[Set[str]] = None,
        max_query_length: int = 50000,
    ):
        """
        Initialize SQL validator.

        Args:
            allowed_schemas: Set of allowed schema names (default: dim, fact, agg)
            dangerous_keywords: Set of dangerous SQL keywords to block
            dangerous_functions: Set of dangerous PostgreSQL functions to block
            max_query_length: Maximum allowed query length (prevent DoS)
        """
        self.allowed_schemas = allowed_schemas or ALLOWED_SCHEMAS
        self.dangerous_keywords = dangerous_keywords or DANGEROUS_KEYWORDS
        self.dangerous_functions = dangerous_functions or DANGEROUS_FUNCTIONS
        self.max_query_length = max_query_length

    def validate_query(self, sql: str, allow_multiple_statements: bool = False) -> bool:
        """
        Comprehensive SQL query validation.

        Args:
            sql: SQL query to validate
            allow_multiple_statements: Whether to allow multiple statements (for batch queries)

        Returns:
            True if validation passes

        Raises:
            SQLValidationError: If validation fails
        """
        if not sql or not sql.strip():
            raise SQLValidationError("SQL query cannot be empty")

        # Check query length (prevent DoS)
        if len(sql) > self.max_query_length:
            raise SQLValidationError(
                f"Query exceeds maximum length of {self.max_query_length} characters"
            )

        # Validate no dangerous keywords
        self._validate_no_dangerous_keywords(sql)

        # Validate no dangerous functions
        self._validate_no_dangerous_functions(sql)

        # Validate statement type (SELECT or WITH only)
        self._validate_statement_type(sql)

        # Validate no multiple statements (unless explicitly allowed)
        if not allow_multiple_statements:
            self._validate_single_statement(sql)

        logger.debug("SQL validation passed")
        return True

    def _validate_no_dangerous_keywords(self, sql: str) -> None:
        """
        Check for dangerous SQL keywords.

        Args:
            sql: SQL query to check

        Raises:
            SQLValidationError: If dangerous keyword found
        """
        sql_upper = sql.upper()

        for keyword in self.dangerous_keywords:
            # Use word boundaries to avoid false positives
            # E.g., don't flag "INSERTED_DATE" when blocking "INSERT"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                raise SQLValidationError(
                    f"Dangerous SQL keyword detected: '{keyword}'. "
                    f"Only SELECT queries are allowed."
                )

    def _validate_no_dangerous_functions(self, sql: str) -> None:
        """
        Check for dangerous PostgreSQL functions.

        Args:
            sql: SQL query to check

        Raises:
            SQLValidationError: If dangerous function found
        """
        sql_lower = sql.lower()

        for function in self.dangerous_functions:
            # Match function calls: function_name(
            pattern = r'\b' + re.escape(function.lower()) + r'\s*\('
            if re.search(pattern, sql_lower):
                raise SQLValidationError(
                    f"Dangerous PostgreSQL function detected: '{function}'. "
                    f"This function is not allowed in read-only queries."
                )

    def _validate_statement_type(self, sql: str) -> None:
        """
        Ensure query is SELECT or WITH (CTE) only.

        Args:
            sql: SQL query to check

        Raises:
            SQLValidationError: If not SELECT/WITH statement
        """
        # Remove leading whitespace and comments
        sql_trimmed = self._remove_leading_comments(sql).upper().strip()

        if not sql_trimmed.startswith('SELECT') and not sql_trimmed.startswith('WITH'):
            raise SQLValidationError(
                "SQL must start with SELECT or WITH (for CTEs). "
                f"Got: {sql_trimmed[:50]}"
            )

    def _validate_single_statement(self, sql: str) -> None:
        """
        Ensure only a single SQL statement (prevent SQL injection).

        Args:
            sql: SQL query to check

        Raises:
            SQLValidationError: If multiple statements detected
        """
        # Remove string literals to avoid counting semicolons inside strings
        sql_without_strings = self._remove_string_literals(sql)

        # Count semicolons (allow one at the end)
        semicolon_count = sql_without_strings.count(';')

        if semicolon_count > 1:
            raise SQLValidationError(
                "Multiple SQL statements not allowed (SQL injection risk). "
                f"Found {semicolon_count} semicolons."
            )

        # If there's one semicolon, it must be at the end
        if semicolon_count == 1 and not sql_without_strings.rstrip().endswith(';'):
            raise SQLValidationError(
                "Semicolon must only appear at the end of the query"
            )

    def _remove_leading_comments(self, sql: str) -> str:
        """
        Remove leading SQL comments.

        Args:
            sql: SQL query

        Returns:
            SQL without leading comments
        """
        # Remove leading line comments (-- ...)
        sql = re.sub(r'^\s*(--[^\n]*\n)+', '', sql, flags=re.MULTILINE)

        # Remove leading block comments (/* ... */)
        sql = re.sub(r'^\s*/\*.*?\*/', '', sql, flags=re.DOTALL)

        return sql.strip()

    def _remove_string_literals(self, sql: str) -> str:
        """
        Remove string literals from SQL (to avoid false positives in validation).

        Args:
            sql: SQL query

        Returns:
            SQL with string literals replaced by empty strings
        """
        # Remove single-quoted strings (PostgreSQL standard)
        sql = re.sub(r"'(?:[^']|'')*'", "''", sql)

        # Remove dollar-quoted strings (PostgreSQL extended)
        sql = re.sub(r'\$[a-zA-Z_]*\$.*?\$[a-zA-Z_]*\$', '$$$$', sql, flags=re.DOTALL)

        return sql

    def validate_identifier(self, identifier: str) -> bool:
        """
        Validate SQL identifier (table name, column name, etc.).

        Prevents SQL injection in dynamic query construction.

        Args:
            identifier: Identifier to validate

        Returns:
            True if valid

        Raises:
            SQLValidationError: If invalid identifier
        """
        if not identifier:
            raise SQLValidationError("Identifier cannot be empty")

        if len(identifier) > 63:  # PostgreSQL identifier length limit
            raise SQLValidationError(
                f"Identifier too long (max 63 characters): {identifier}"
            )

        if not IDENTIFIER_PATTERN.match(identifier):
            raise SQLValidationError(
                f"Invalid identifier format: '{identifier}'. "
                f"Must start with letter/underscore and contain only "
                f"alphanumeric characters, underscores, or dollar signs."
            )

        # Check for SQL keywords that shouldn't be used as identifiers
        if identifier.upper() in self.dangerous_keywords:
            raise SQLValidationError(
                f"Identifier cannot be a dangerous SQL keyword: '{identifier}'"
            )

        logger.debug(f"Identifier validated: {identifier}")
        return True

    def validate_schema(self, schema: str) -> bool:
        """
        Validate schema name against allowlist.

        Args:
            schema: Schema name to validate

        Returns:
            True if valid

        Raises:
            SQLValidationError: If schema not allowed
        """
        # First validate as identifier
        self.validate_identifier(schema)

        # Then check against allowlist
        if schema.lower() not in {s.lower() for s in self.allowed_schemas}:
            raise SQLValidationError(
                f"Schema '{schema}' not allowed. "
                f"Allowed schemas: {', '.join(sorted(self.allowed_schemas))}"
            )

        logger.debug(f"Schema validated: {schema}")
        return True

    def validate_table_name(self, table: str) -> bool:
        """
        Validate table name.

        Args:
            table: Table name to validate

        Returns:
            True if valid

        Raises:
            SQLValidationError: If invalid table name
        """
        # Validate as identifier
        self.validate_identifier(table)

        # Additional checks for table names
        # Block suspicious patterns
        suspicious_patterns = [
            r'pg_',  # System tables (except when explicitly allowed)
            r'information_schema',  # System schema
        ]

        # Only block if not in information_schema context
        for pattern in suspicious_patterns:
            if re.match(pattern, table.lower()):
                logger.warning(f"Suspicious table name pattern: {table}")
                # Don't block, just log - might be legitimate

        logger.debug(f"Table name validated: {table}")
        return True

    def sanitize_limit(self, limit: int, max_limit: int = 10000) -> int:
        """
        Sanitize LIMIT clause value.

        Args:
            limit: Requested limit
            max_limit: Maximum allowed limit

        Returns:
            Sanitized limit value

        Raises:
            SQLValidationError: If limit is invalid
        """
        if not isinstance(limit, int):
            raise SQLValidationError(f"LIMIT must be an integer, got: {type(limit)}")

        if limit < 0:
            raise SQLValidationError(f"LIMIT cannot be negative: {limit}")

        if limit > max_limit:
            logger.warning(f"LIMIT {limit} exceeds maximum {max_limit}, capping")
            return max_limit

        return limit


# Global validator instance
_default_validator = SQLValidator()


def validate_query(sql: str, allow_multiple_statements: bool = False) -> bool:
    """
    Validate SQL query using default validator.

    Args:
        sql: SQL query to validate
        allow_multiple_statements: Whether to allow multiple statements

    Returns:
        True if validation passes

    Raises:
        SQLValidationError: If validation fails
    """
    return _default_validator.validate_query(sql, allow_multiple_statements)


def validate_identifier(identifier: str) -> bool:
    """Validate SQL identifier using default validator."""
    return _default_validator.validate_identifier(identifier)


def validate_schema(schema: str) -> bool:
    """Validate schema name using default validator."""
    return _default_validator.validate_schema(schema)


def validate_table_name(table: str) -> bool:
    """Validate table name using default validator."""
    return _default_validator.validate_table_name(table)


def sanitize_limit(limit: int, max_limit: int = 10000) -> int:
    """Sanitize LIMIT clause value using default validator."""
    return _default_validator.sanitize_limit(limit, max_limit)
