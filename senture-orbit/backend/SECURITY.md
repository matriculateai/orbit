# SQL Security Documentation

This document describes the SQL security measures implemented in the Senture Orbit backend to ensure all database queries are read-only and safe from SQL injection attacks.

## Overview

The application implements **defense-in-depth** security with multiple layers:

1. **SQL Query Validation** - Blocks dangerous SQL operations at the application level
2. **Read-Only Transactions** - Enforces read-only access at the database level
3. **Identifier Validation** - Prevents SQL injection in dynamic queries
4. **Schema Whitelisting** - Restricts access to approved database schemas
5. **Query Length Limits** - Prevents DoS attacks via excessively long queries

## Security Layers

### Layer 1: SQL Query Validation

**Location:** `app/security/sql_validator.py`

All SQL queries are validated before execution using the `SQLValidator` class:

#### Dangerous Keyword Blocking

Blocks dangerous SQL operations including:
- **Data Modification:** DROP, DELETE, UPDATE, INSERT, TRUNCATE, MERGE
- **Schema Modification:** ALTER, CREATE, RENAME
- **Security & Permissions:** GRANT, REVOKE
- **Transaction Control:** COMMIT, ROLLBACK, BEGIN, START
- **Execution:** EXECUTE, EXEC, CALL
- **Variables:** DECLARE, SET
- **Database Operations:** VACUUM, ANALYZE, CLUSTER, REINDEX
- **Prepared Statements:** PREPARE, DEALLOCATE
- **Locking:** LOCK
- **File Operations:** COPY
- **System:** LOAD, IMPORT

#### Dangerous Function Blocking

Blocks dangerous PostgreSQL functions including:
- **File System Access:** pg_read_file, pg_write_file, pg_ls_dir, pg_stat_file
- **Process Control:** pg_sleep, pg_sleep_for, pg_sleep_until
- **Administrative:** pg_terminate_backend, pg_cancel_backend, pg_reload_conf
- **Large Objects:** lo_import, lo_export, lo_create, lo_unlink
- **Extensions:** pg_create_extension, pg_drop_extension

#### Statement Type Enforcement

- Only `SELECT` and `WITH` (Common Table Expressions) statements are allowed
- Queries must start with SELECT or WITH after removing leading comments

#### Multiple Statement Prevention

- Only a single SQL statement is allowed per query
- Prevents SQL injection via statement chaining
- Semicolons are only permitted at the end of queries

#### Query Length Limits

- Maximum query length: 50,000 characters (configurable via `SQL_MAX_QUERY_LENGTH`)
- Prevents DoS attacks via excessively long queries

### Layer 2: Read-Only Transactions

**Location:** `app/services/postgres.py`

All queries are executed within **read-only transactions**:

```python
async with conn.transaction(readonly=True):
    rows = await conn.fetch(query, *(params or []))
```

**Benefits:**
- Database-level enforcement that no modifications can occur
- Prevents data modification even if validation is bypassed
- PostgreSQL will reject any write operations within the transaction

### Layer 3: Identifier Validation

**Location:** `app/security/sql_validator.py`

Schema and table names are validated before use in dynamic queries:

#### Identifier Pattern Validation

Valid identifiers must:
- Start with a letter or underscore
- Contain only alphanumeric characters, underscores, or dollar signs
- Be 63 characters or less (PostgreSQL limit)
- Not be dangerous SQL keywords

#### Schema Whitelisting

Only these schemas are allowed:
- `dim` - Dimension tables
- `fact` - Fact tables
- `agg` - Aggregated views
- `information_schema` - PostgreSQL metadata (read-only)

Configurable via `SQL_ALLOWED_SCHEMAS` in settings.

### Layer 4: Parameterized Queries

Where possible, queries use PostgreSQL's parameterized query syntax:

```python
query = "SELECT * FROM information_schema.columns WHERE table_schema = $1"
await conn.fetch(query, schema_name)
```

**Benefits:**
- PostgreSQL handles parameter escaping
- Completely prevents SQL injection in parameter values
- Note: Schema/table names cannot be parameterized, hence the need for validation

### Layer 5: Application-Level Controls

#### Query Result Limits

- Maximum rows per query: 10,000 (configurable via `SQL_MAX_RESULT_ROWS`)
- Prevents memory exhaustion from overly large result sets

#### Skip Validation Flag

The `skip_validation` parameter allows bypassing validation for **trusted internal queries only**:

```python
# Internal health check - safe to skip validation
result = await postgres.execute_query(
    "SELECT 1 as health_check",
    skip_validation=True
)
```

**Usage Guidelines:**
- Only use for hardcoded, trusted queries
- Never use with user input
- Only use for internal system queries (health checks, metadata queries)

## Security Validation Flow

### Chat Endpoint Query Flow

```
User Question
    ↓
ClaudeService.generate_sql()
    ↓
ClaudeService.validate_sql_safety() [Layer 1: Keyword/Function Check]
    ↓
PostgresService.execute_query()
    ↓
SQLValidator.validate_query() [Layer 1: Full Validation]
    ↓
conn.transaction(readonly=True) [Layer 2: DB-Level Enforcement]
    ↓
Execute Query
    ↓
Return Results
```

### Dynamic Table Query Flow (e.g., get_table_info)

```
User Provides Schema/Table
    ↓
validate_schema(schema) [Layer 3: Identifier Validation + Whitelist]
    ↓
validate_table_name(table) [Layer 3: Identifier Validation]
    ↓
Build Query with Validated Identifiers
    ↓
execute_query(skip_validation=True) [Validation already done]
    ↓
conn.transaction(readonly=True) [Layer 2: DB-Level Enforcement]
    ↓
Execute Query
    ↓
Return Results
```

## Security Best Practices

### For Developers

1. **Always validate user input** - Even if you think it's safe
2. **Use parameterized queries** - When parameter values are involved
3. **Validate identifiers** - When schema/table names come from users
4. **Never skip validation** - Unless for hardcoded internal queries
5. **Review SQL generation** - Ensure Claude isn't being prompt-injected

### For Operations

1. **Use read-only database user** - Additional security layer at DB level
2. **Monitor query patterns** - Watch for suspicious queries in logs
3. **Keep SQL_ENABLE_VALIDATION=true** - Never disable in production
4. **Review allowed schemas** - Only add schemas that should be queryable
5. **Set appropriate limits** - Adjust `SQL_MAX_QUERY_LENGTH` and `SQL_MAX_RESULT_ROWS` based on needs

## Configuration

### Environment Variables

```bash
# SQL Security Settings
SQL_MAX_QUERY_LENGTH=50000         # Max query length (prevent DoS)
SQL_MAX_RESULT_ROWS=10000          # Max rows per query (prevent memory exhaustion)
SQL_ENABLE_VALIDATION=true         # Enable SQL validation (always true in prod)
SQL_ALLOWED_SCHEMAS=["dim","fact","agg","information_schema"]
```

## Testing Security

### Test Dangerous Queries (Should All Fail)

```python
from app.security import validate_query, SQLValidationError

# Should raise SQLValidationError
test_cases = [
    "DROP TABLE users",
    "DELETE FROM customers",
    "UPDATE products SET price = 0",
    "INSERT INTO logs VALUES ('hack')",
    "SELECT * FROM users; DROP TABLE users;--",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT pg_sleep(1000)",
]

for sql in test_cases:
    try:
        validate_query(sql)
        print(f"❌ SECURITY FAILURE: Query should have been blocked: {sql}")
    except SQLValidationError:
        print(f"✅ Blocked: {sql}")
```

### Test Valid Queries (Should All Pass)

```python
# Should all pass
valid_queries = [
    "SELECT * FROM dim.product",
    "SELECT COUNT(*) FROM fact.secondary_sales_daily",
    "WITH top_products AS (SELECT * FROM dim.product) SELECT * FROM top_products",
    "SELECT * FROM agg.kpi_dashboard WHERE dsoh_days < 45",
]

for sql in valid_queries:
    try:
        validate_query(sql)
        print(f"✅ Allowed: {sql}")
    except SQLValidationError as e:
        print(f"❌ SECURITY FAILURE: Valid query blocked: {sql} - {e}")
```

### Test Identifier Validation

```python
from app.security import validate_schema, validate_table_name, SQLValidationError

# Valid identifiers
validate_schema("dim")  # ✅ Pass
validate_table_name("product")  # ✅ Pass

# Invalid identifiers (SQL injection attempts)
try:
    validate_schema("dim; DROP TABLE users--")  # ❌ Should fail
except SQLValidationError:
    print("✅ SQL injection attempt blocked")

try:
    validate_table_name("product' OR '1'='1")  # ❌ Should fail
except SQLValidationError:
    print("✅ SQL injection attempt blocked")

# Unauthorized schema
try:
    validate_schema("pg_catalog")  # ❌ Should fail (not in whitelist)
except SQLValidationError:
    print("✅ Unauthorized schema blocked")
```

## Known Limitations

1. **Comment-based obfuscation** - Advanced SQL comment techniques might bypass keyword detection
   - **Mitigation:** String literal removal and comment stripping in validation

2. **Schema/table name parameterization** - PostgreSQL doesn't support parameterized identifiers
   - **Mitigation:** Strict identifier validation and whitelisting

3. **Claude prompt injection** - Carefully crafted prompts might trick Claude into generating dangerous SQL
   - **Mitigation:** Multi-layer validation catches any dangerous SQL regardless of source

4. **Resource exhaustion** - Complex queries can still consume resources even if read-only
   - **Mitigation:** Query timeouts (30s), row limits (10,000), connection pooling

## Incident Response

If you suspect a security bypass:

1. **Immediate Actions:**
   - Check application logs for validation failures
   - Review PostgreSQL query logs for unexpected patterns
   - Verify `SQL_ENABLE_VALIDATION=true` in production

2. **Investigation:**
   - Identify the attack vector (which endpoint, what input)
   - Test the bypass in a development environment
   - Determine if data was compromised (check DB audit logs)

3. **Remediation:**
   - Update validation rules to block the bypass
   - Deploy hotfix immediately
   - Notify security team and affected users

4. **Prevention:**
   - Add regression test for the bypass attempt
   - Review similar code patterns
   - Update this documentation with new attack vector

## Additional Database-Level Security (Recommended)

### Create Read-Only Database User

```sql
-- Create read-only role
CREATE ROLE orbit_readonly;

-- Grant CONNECT privilege
GRANT CONNECT ON DATABASE postgres TO orbit_readonly;

-- Grant USAGE on schemas
GRANT USAGE ON SCHEMA dim, fact, agg TO orbit_readonly;

-- Grant SELECT on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA dim, fact, agg TO orbit_readonly;

-- Grant SELECT on future tables (for new tables)
ALTER DEFAULT PRIVILEGES IN SCHEMA dim, fact, agg
GRANT SELECT ON TABLES TO orbit_readonly;

-- Create application user with read-only role
CREATE USER orbit_app WITH PASSWORD 'secure_password_here';
GRANT orbit_readonly TO orbit_app;
```

Update `.env` to use the read-only user:
```bash
POSTGRES_USER=orbit_app
POSTGRES_PASSWORD=secure_password_here
```

**Benefits:**
- Additional enforcement at the database level
- Even if application security is bypassed, database user can't modify data
- Follows principle of least privilege

## References

- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [PostgreSQL Security Best Practices](https://www.postgresql.org/docs/current/sql-security.html)
- [asyncpg Security](https://magicstack.github.io/asyncpg/current/usage.html#connection-pools)

## Version History

- **v2.0.0** (2025-12-19) - Comprehensive security implementation
  - Multi-layer SQL validation
  - Read-only transaction enforcement
  - Identifier validation and schema whitelisting
  - SQL injection vulnerability fixes
