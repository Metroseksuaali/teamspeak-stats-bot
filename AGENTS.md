# AI Agent Guidelines for TeamSpeak Stats Bot

This document provides instructions for AI agents (like GitHub Codex, PR reviewers, etc.) working on this codebase.

## For Code Review Agents (e.g., Codex)

### ❌ DO NOT

- **DO NOT** commit or push changes to the repository
- **DO NOT** apply changes directly to files
- **DO NOT** modify git configuration
- **DO NOT** run destructive operations

### ✅ DO

- **DO** analyze code for bugs, security issues, and best practices
- **DO** provide all findings in a single comprehensive comment/response
- **DO** suggest improvements with clear explanations
- **DO** include severity levels (P0/Critical, P1/High, P2/Medium, P3/Low)
- **DO** provide code examples in suggestions when helpful

### Response Format

When reviewing code, structure your feedback as:

```markdown
## Summary
[Brief overview of findings]

## Critical Issues (P0)
- Issue 1: [Description]
  - Location: file.py:123
  - Impact: [What breaks]
  - Suggestion: [How to fix]

## High Priority (P1)
- Issue 1: [Description]
  ...

## Medium Priority (P2)
- Issue 1: [Description]
  ...

## Low Priority (P3) / Suggestions
- Suggestion 1: [Description]
  ...

## Testing
[What testing was performed, e.g., syntax check, linting]
```

### Example Good Review

```markdown
## Summary
Found 1 critical bug in API initialization and 2 medium-priority improvements.

## Critical Issues (P0)

**PostgreSQL backend configuration ignored**
- Location: ts_activity_bot/api.py:41-47
- Impact: When `backend: postgresql` is set, the API still uses SQLite
- Root cause: API instantiates `Database(config.database.path)` instead of `create_database(config)`
- Fix: Replace `db = Database(config.database.path)` with `db = create_database(config)`

## Testing
✅ python -m compileall ts_activity_bot
✅ Verified SQL syntax in stats.py:962-1024
```

### Code Quality Checks

When reviewing, check for:

1. **Security**
   - SQL injection vulnerabilities
   - API key exposure
   - Input validation
   - Authentication bypass

2. **Correctness**
   - Type errors
   - Logic bugs
   - Edge cases (None, empty lists, division by zero)
   - SQL syntax errors

3. **Performance**
   - N+1 queries
   - Missing indexes
   - Inefficient algorithms

4. **Maintainability**
   - Code duplication
   - Unclear naming
   - Missing error handling
   - Incomplete documentation

## For Development Agents (e.g., Claude Code)

### Workflow

1. Read user requirements
2. Plan implementation (use TODO list)
3. Make changes to code
4. Test changes (compileall, syntax checks)
5. Commit with clear messages
6. Push to feature branch

### Commit Messages

Follow this format:

```
[Type]: [Short description]

[Detailed explanation of changes]

[Why these changes were needed]

[Testing performed]
```

Types: `Fix`, `Feature`, `Refactor`, `Docs`, `Test`, `Chore`

### Branch Naming

- Feature branches: `claude/feature-name-<session-id>`
- Bug fixes: `claude/fix-issue-name-<session-id>`
- Always include session ID at the end

## Technology Stack

This project uses:
- **Python 3.11+** with type hints
- **FastAPI** for REST API
- **Strawberry GraphQL** for GraphQL API
- **SQLite** (default) or **PostgreSQL** for database
- **Prometheus** for metrics
- **Docker** for deployment

## Architecture Notes

### Database Backends

- `Database` (SQLite): Full support for all features
- `PostgreSQLBackend`: Write operations only (poller)
- `StatsCalculator`: SQLite-specific analytics (uses `?` placeholders)

When adding database features:
1. Add method to `DatabaseBackend` (abstract interface)
2. Implement in both `Database` (SQLite) and `PostgreSQLBackend`
3. Test with both backends
4. Document any backend-specific limitations

### Key Design Patterns

- **Factory pattern**: `create_database()` for backend selection
- **Context managers**: All database operations use `with` statements
- **Dependency injection**: FastAPI endpoints use `Depends()`
- **Pydantic models**: All config and API models

## Testing Guidelines

Before committing:

```bash
# Syntax check
python -m compileall ts_activity_bot

# Type check (if mypy is installed)
mypy ts_activity_bot

# Import test
python -c "from ts_activity_bot import api, poller, stats"

# Config validation
python -c "from ts_activity_bot.config import get_config; get_config()"
```

## Common Pitfalls

1. **SQL Placeholders**: Use `?` for SQLite, `%s` for PostgreSQL
2. **Window Functions**: SQLite doesn't support window functions inside aggregates
3. **Connection Pooling**: PostgreSQL uses connection pools, SQLite doesn't
4. **Integer Size**: Use `BIGINT` in PostgreSQL, `INTEGER` in SQLite for timestamps
5. **Auto-increment**: `AUTOINCREMENT` (SQLite) vs `SERIAL`/`BIGSERIAL` (PostgreSQL)

## Questions?

See also:
- `claude.md` - Guidelines for Claude Code specifically
- `README.md` - Project documentation
- `CONTRIBUTING.md` - Contribution guidelines (if exists)

---

**Last updated**: 2025-11-15
