# Claude Code Guidelines for TeamSpeak Stats Bot

Guidelines specifically for Claude Code (Anthropic's AI coding assistant) when working on this project.

## Project Overview

This is a **TeamSpeak server activity tracking bot** with:
- Data collection (poller) that snapshots server state every 30-60 seconds
- Multi-backend database (SQLite default, PostgreSQL optional)
- Triple interface: CLI, REST API, GraphQL API
- Analytics and statistics calculation
- Prometheus metrics export

## Your Role

You (Claude Code) are responsible for:
- ✅ Implementing new features
- ✅ Fixing bugs
- ✅ Refactoring code
- ✅ Writing documentation
- ✅ Creating commits and pushing to feature branches
- ✅ Responding to user requests and Codex feedback

## Branch Strategy

**IMPORTANT**: Always work on feature branches with session ID:

```bash
# Current branch for this session:
claude/prometheus-postgres-support-011Ew7RaDSxnT3KSGW5ZYdiv

# Pattern:
claude/<feature-description>-<session-id>
```

- ❌ NEVER commit to `main` or `master`
- ❌ NEVER push with `--force` unless explicitly requested
- ✅ Create descriptive branch names
- ✅ Always include session ID at the end

## Working with Codex

**Codex is a code review agent** - treat its feedback as valuable PR review:

1. **Codex will NOT make changes** - it only analyzes and suggests
2. **You implement Codex's suggestions** - read its feedback and apply fixes
3. **Address all P0/Critical issues** before pushing
4. **Consider P1/High and P2/Medium issues** - discuss with user if unsure
5. **P3/Low suggestions are optional** - use judgment

### When Codex Reports Issues

```markdown
User: "Codex found 3 bugs in api.py"

Your response:
1. Read Codex's feedback carefully
2. Understand each issue
3. Fix the issues in code
4. Test the fixes (compileall, imports)
5. Commit with clear message referencing Codex feedback
6. Push to branch
7. Confirm to user what was fixed
```

**Example**:
```
Fixed 3 issues from Codex review:
- P0: PostgreSQL backend not used (api.py:47)
- P1: Missing error handling in metrics (metrics.py:89)
- P2: Type hint incorrect (stats.py:123)

Commit: abc1234
```

## Commit Message Format

Use this structure:

```
[Type]: [Clear one-line description]

[Detailed explanation of what changed]

[Why it was changed - reference Codex feedback if applicable]

[Testing performed]

[Related issues or PR numbers if applicable]
```

### Examples

**Good commit**:
```
Fix: Address Codex feedback on PostgreSQL backend initialization

Changes:
- API now uses create_database() factory instead of Database()
- Poller updated to use factory method
- Added conditional stats_calc initialization (SQLite only)
- GraphQL router registration skipped when PostgreSQL is active

Addresses Codex P0 issue: PostgreSQL configuration was ignored.
Stats endpoints now return HTTP 503 for PostgreSQL deployments.

Testing:
✅ python -m compileall ts_activity_bot
✅ Verified SQLite backend still works
✅ Verified PostgreSQL backend initializes correctly
```

**Bad commit**:
```
fix stuff

fixed things codex said
```

## Code Style

### Follow existing patterns:

```python
# ✅ Good
def get_user_stats(self, client_uid: str, days: Optional[int] = None) -> Dict[str, any]:
    """
    Get detailed statistics for a specific user.

    Args:
        client_uid: Unique client identifier
        days: Number of days to analyze (None = all time)

    Returns:
        dict: User statistics including online time, channels, etc.

    Raises:
        ValueError: If client_uid is invalid
    """
    if not client_uid:
        raise ValueError("client_uid cannot be empty")

    # Implementation...

# ❌ Bad
def get_user_stats(client_uid, days=None):
    # no docstring, no types
    return stats
```

### Database Operations

```python
# ✅ Good - Use context manager
with self.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()

# ❌ Bad - Manual connection management
conn = self.get_connection()
cursor = conn.cursor()
cursor.execute(query)
return cursor.fetchall()
# (forgot to close!)
```

### Error Handling

```python
# ✅ Good - Specific exceptions, logging
try:
    result = self.stats_calc.get_summary(days=7)
    return result
except ValueError as e:
    logger.error(f"Invalid days parameter: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"Failed to get summary: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")

# ❌ Bad - Bare except, no logging
try:
    result = stats_calc.get_summary(days=7)
    return result
except:
    return None
```

## Testing Before Commit

**Always run before committing**:

```bash
# 1. Syntax check (REQUIRED)
python -m compileall ts_activity_bot

# 2. Import check (REQUIRED)
python -c "from ts_activity_bot import api, poller, stats, db"

# 3. Config validation (REQUIRED if config changes)
python -c "from ts_activity_bot.config import get_config; get_config()"

# 4. Run specific functionality if changed
# Example: Test database factory
python -c "
from ts_activity_bot.config import get_config
from ts_activity_bot.db import create_database
config = get_config()
db = create_database(config)
print('Database initialized:', type(db).__name__)
"
```

## Common Tasks

### Adding a New API Endpoint

1. Define Pydantic response model
2. Add endpoint function with docstring
3. Add authentication (`Depends(verify_api_key)`)
4. Implement using `stats_calc` or `db`
5. Handle errors properly
6. Update README.md API endpoints table
7. Test endpoint manually or with curl

### Adding Database Backend Feature

1. Add abstract method to `DatabaseBackend` (db_base.py)
2. Implement in `Database` (db.py) - SQLite version
3. Implement in `PostgreSQLBackend` (db_postgres.py)
4. Test both backends
5. Document any limitations

### Adding a CLI Command

1. Add command to `cli.py` using `@cli.command()`
2. Use Rich for beautiful output
3. Handle errors gracefully
4. Update README.md CLI commands section
5. Test command with various parameters

## Database Backend Notes

### Current Architecture

```
┌─────────────────┐
│  Poller         │──→ create_database() ──→ SQLite OR PostgreSQL
└─────────────────┘                          (writes snapshots)

┌─────────────────┐
│  API /health    │──→ db (from factory) ──→ SQLite OR PostgreSQL
│  API /database  │                          (basic queries)
└─────────────────┘

┌─────────────────┐
│  API /stats/*   │──→ stats_calc ────────→ SQLite ONLY
│  GraphQL        │                          (complex analytics)
│  CLI            │
└─────────────────┘
```

### Why Stats are SQLite-only

`StatsCalculator` uses SQLite-specific SQL:
- Placeholder syntax: `?` instead of `%s`
- Window function limitations
- Specific aggregate behaviors
- JSON functions

**Future work**: Refactor `StatsCalculator` to use `DatabaseBackend` interface.

## Documentation Standards

When adding features:

1. **Code docstrings** - Every public function/method
2. **README.md** - User-facing feature documentation
3. **config.example.yaml** - If new config options
4. **CHANGELOG.md** - If exists, document changes
5. **Type hints** - All parameters and return values

## User Communication

### Be concise and clear

```markdown
✅ Good:
"Lisäsin Prometheus metrics endpointin (/metrics).
Commit: abc1234
Branch: claude/prometheus-support-xyz

Testit:
✅ python -m compileall ts_activity_bot
✅ curl http://localhost:8080/metrics"

❌ Bad:
"I have implemented the feature you requested by adding
a new endpoint to the API server which will expose metrics
in the Prometheus format that can be scraped by your
monitoring infrastructure..."
(too verbose)
```

### When you don't understand

```markdown
✅ Good:
"En ole varma ymmärsinkö oikein - haluatko että:
1. PostgreSQL korvaa SQLiten kokonaan, VAI
2. PostgreSQL on vaihtoehto rinnalla?

Voitko tarkentaa?"

❌ Bad:
*Implements something without clarifying*
*Makes wrong assumptions*
```

## Security Considerations

**Always check for**:

1. **SQL Injection**
   - Use parameterized queries: `cursor.execute(query, params)`
   - NEVER: `f"SELECT * FROM users WHERE id = {user_id}"`

2. **API Key Exposure**
   - Never log API keys
   - Never commit API keys
   - Use environment variables in examples

3. **Path Traversal**
   - Validate file paths
   - Use `Path.resolve()` and check if under allowed directory

4. **Input Validation**
   - Validate all user inputs
   - Check ranges (days >= 0, limit <= max)
   - Sanitize strings

## Performance Considerations

1. **Database Queries**
   - Use indexes for WHERE clauses
   - Avoid N+1 queries
   - Use aggregates in SQL, not Python loops

2. **API Responses**
   - Add pagination for large datasets
   - Consider adding `limit` parameters
   - Cache expensive calculations

3. **Memory Usage**
   - Don't load entire tables into memory
   - Use generators for large datasets
   - Close database connections properly

## Questions to Ask Yourself

Before implementing:
- [ ] Do I understand the requirement?
- [ ] What edge cases exist?
- [ ] How will this work with both SQLite and PostgreSQL?
- [ ] What can go wrong?
- [ ] How will I test this?

Before committing:
- [ ] Did I run compileall?
- [ ] Did I test the changes?
- [ ] Is the commit message clear?
- [ ] Did I update documentation?
- [ ] Did I address all Codex feedback?

## When Stuck

1. **Read existing code** - Similar features already implemented
2. **Check imports** - Required dependencies installed?
3. **Ask user** - Better to clarify than guess wrong
4. **Simplify** - Start with basic version, iterate

## Remember

- 🇫🇮 User prefers Finnish for communication
- 🧪 Codex is your code reviewer - respect its feedback
- 🚫 Never push to main/master
- ✅ Always test before committing
- 📝 Document user-facing changes
- 🤔 When in doubt, ask

---

**Last updated**: 2025-11-15
**Project**: TeamSpeak Stats Bot v2.0
**Your session**: claude/prometheus-postgres-support-011Ew7RaDSxnT3KSGW5ZYdiv
