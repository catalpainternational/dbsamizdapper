# Testing Guide

This guide provides comprehensive instructions for running tests in the dbsamizdapper project.

## Quick Start

For the fastest way to get tests running, see the [Quick Test Setup](#quick-test-setup) section below.

## Table of Contents

- [Quick Test Setup](#quick-test-setup)
- [Test Types](#test-types)
- [Database Setup](#database-setup)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Test Markers](#test-markers)
- [Coverage](#coverage)

---

## Quick Test Setup

### 1. Start PostgreSQL Database

**Option A: Using Docker Compose (Recommended)**
```bash
docker-compose up -d
```

**Option B: Using Docker**
```bash
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15
```

**Option C: Using Podman**
```bash
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15
```

### 2. Set Database Connection

**Option A: Environment Variable**
```bash
export DB_URL=postgresql://postgres@localhost:5435/postgres
```

**Option B: Create `.env` File**

Create a `.env` file in the project root:
```bash
# Copy this content to .env file
DB_URL=postgresql://postgres@localhost:5435/postgres
```

The test suite automatically loads `.env` files using `python-dotenv`.

**Note**: A `.env.example` file should exist in the repository as a template. If it doesn't, create `.env` with the content above.

### 3. Run Tests

```bash
# All tests (requires database)
uv run pytest

# Unit tests only (no database required)
uv run pytest -m unit

# Integration tests only (requires database)
uv run pytest -m integration
```

---

## Test Types

The test suite includes two main types of tests:

### Unit Tests

- **No database required**
- Test pure functions, logic, and data structures
- Fast execution
- Marked with `@pytest.mark.unit`

**Run unit tests:**
```bash
uv run pytest -m unit
```

### Integration Tests

- **Require a running PostgreSQL database**
- Test database operations, views, triggers, functions
- Test CLI commands end-to-end
- Marked with `@pytest.mark.integration`

**Run integration tests:**
```bash
# Make sure database is running first!
uv run pytest -m integration
```

---

## Database Setup

### Connection String Format

The database connection string follows PostgreSQL's standard format:

```
postgresql://[user[:password]@][host][:port][/database]
```

**Examples:**
- `postgresql://postgres@localhost:5435/postgres` - Default test database
- `postgresql://user:pass@localhost:5432/mydb` - With password
- `postgresql:///mydb` - Local socket connection (no host)

**Important**: When specifying a host (like `localhost`), use **double slash** (`//`), not triple slash (`///`).

### Default Configuration

The test suite defaults to:
- **Host**: `localhost`
- **Port**: `5435`
- **User**: `postgres`
- **Password**: (none, uses trust authentication)
- **Database**: `postgres`

This matches the default Docker Compose configuration.

### Changing the Port

If port 5435 is already in use:

1. **Update `docker-compose.yml`:**
   ```yaml
   ports:
     - "5436:5432"  # Change 5435 to 5436
   ```

2. **Update `DB_URL`:**
   ```bash
   export DB_URL=postgresql://postgres@localhost:5436/postgres
   ```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_api.py

# Run specific test function
uv run pytest tests/test_api.py::test_sync_basic

# Run tests matching a pattern
uv run pytest -k "test_sync"
```

### Test Markers

```bash
# Unit tests only
uv run pytest -m unit

# Integration tests only
uv run pytest -m integration

# Django tests only
uv run pytest -m django

# Slow tests
uv run pytest -m slow

# Exclude integration tests
uv run pytest -m "not integration"
```

### Coverage

```bash
# Run tests with coverage report
uv run pytest --cov=dbsamizdat --cov-report=term-missing

# Generate HTML coverage report
uv run pytest --cov=dbsamizdat --cov-report=html
# Open htmlcov/index.html in browser

# Generate XML coverage report (for CI)
uv run pytest --cov=dbsamizdat --cov-report=xml
```

### Parallel Execution

```bash
# Install pytest-xdist first: uv add --group dev pytest-xdist
uv run pytest -n auto  # Use all CPU cores
```

---

## Environment Variables

The test suite supports the following environment variables:

### `DB_URL` (Primary)

Primary database connection string.

```bash
export DB_URL=postgresql://postgres@localhost:5435/postgres
```

### `DBURL` (Alternative)

Alternative name for database URL (for compatibility).

```bash
export DBURL=postgresql://postgres@localhost:5435/postgres
```

**Priority**: `DB_URL` takes precedence over `DBURL` if both are set.

### Loading from `.env` File

The test suite automatically loads environment variables from `.env` files using `python-dotenv`.

Create a `.env` file in the project root:
```bash
DB_URL=postgresql://postgres@localhost:5435/postgres
```

**Note**: `.env` files are gitignored. Create a `.env.example` file as a template for other developers.

---

## Troubleshooting

### Connection Refused

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:
1. Verify PostgreSQL is running:
   ```bash
   docker ps  # Should show postgres container
   # Or
   docker-compose ps
   ```

2. Check port is correct:
   ```bash
   # Should show postgres listening on 5435
   netstat -an | grep 5435
   # Or
   lsof -i :5435
   ```

3. Verify connection string format:
   ```bash
   echo $DB_URL
   # Should be: postgresql://postgres@localhost:5435/postgres
   ```

### Authentication Failed

**Error**: `psycopg2.OperationalError: password authentication failed`

**Solutions**:
1. Check connection string format (no password needed with trust auth):
   ```bash
   # Correct (no password):
   postgresql://postgres@localhost:5435/postgres
   
   # Wrong (has password):
   postgresql://postgres:password@localhost:5435/postgres
   ```

2. Verify Docker container uses trust authentication:
   ```bash
   docker run -e POSTGRES_HOST_AUTH_METHOD=trust ...
   ```

### Port Already in Use

**Error**: `Bind for 0.0.0.0:5435 failed: port is already allocated`

**Solutions**:
1. Stop existing container:
   ```bash
   docker ps  # Find container ID
   docker stop <container-id>
   ```

2. Use different port:
   - Update `docker-compose.yml` port mapping
   - Update `DB_URL` to match new port

### Database Does Not Exist

**Error**: `psycopg2.OperationalError: database "postgres" does not exist`

**Solutions**:
1. Use default `postgres` database (created automatically)
2. Or create database manually:
   ```bash
   docker exec -it <container-id> psql -U postgres
   CREATE DATABASE testdb;
   ```

### Tests Hang or Timeout

**Solutions**:
1. Check database is healthy:
   ```bash
   docker exec <container-id> pg_isready -U postgres
   ```

2. Check database logs:
   ```bash
   docker logs <container-id>
   ```

3. Restart database:
   ```bash
   docker-compose restart
   ```

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'dbsamizdat'`

**Solutions**:
1. Install in development mode:
   ```bash
   uv sync --group dev --group testing
   ```

2. Verify Python path:
   ```bash
   uv run python -c "import dbsamizdat; print(dbsamizdat.__file__)"
   ```

---

## Test Markers

The test suite uses pytest markers to categorize tests:

| Marker | Description | Database Required |
|--------|-------------|-------------------|
| `unit` | Unit tests (pure functions) | No |
| `integration` | Integration tests (database operations) | Yes |
| `django` | Django integration tests | Yes |
| `slow` | Slow-running tests (>1 second) | Maybe |
| `requires_schema` | Tests needing custom schema | Yes |

**Usage:**
```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Exclude slow tests
uv run pytest -m "not slow"
```

---

## Coverage

### Current Coverage

The project maintains **55% minimum coverage** (enforced in CI).

### Viewing Coverage

```bash
# Terminal report
uv run pytest --cov=dbsamizdat --cov-report=term-missing

# HTML report (opens in browser)
uv run pytest --cov=dbsamizdat --cov-report=html
open htmlcov/index.html

# XML report (for CI tools)
uv run pytest --cov=dbsamizdat --cov-report=xml
```

### Coverage Configuration

Coverage settings are configured in `pyproject.toml`:
- Source: `dbsamizdat` package
- Excluded: `tests/`, `sample_app/`, `examples/`
- Fail under: 55% (configured in `pytest.ini`)

---

## Test Fixtures

The test suite provides several reusable fixtures (see `tests/conftest.py`):

### `db_args`
Database connection arguments (session-scoped).

### `clean_db`
Provides a clean database for each test (automatically nukes before/after).

### `db_cursor`
Provides a database cursor for single operations.

### `test_schema`
Creates and cleans up a test schema.

### `fruit_pet_tables`
Creates sample Fruit and Pet tables with data.

### `refresh_trigger_tables`
Creates tables `d` and `d2` for refresh trigger tests.

### `django_setup`
Configures Django environment for Django tests.

**Example Usage:**
```python
def test_something(clean_db):
    """Test that requires clean database"""
    from dbsamizdat.runner import cmd_sync
    cmd_sync(clean_db, [MyView])
```

---

## Continuous Integration

Tests run automatically in GitHub Actions on:
- Every push to `main`
- Every pull request

The CI workflow:
1. Tests on Python 3.12, 3.13, 3.14
2. Runs linting (ruff)
3. Runs type checking (mypy)
4. Runs all tests with PostgreSQL service
5. Checks coverage threshold

See `.github/workflows/pytest.yaml` for details.

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [PostgreSQL Connection Strings](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup guide
- [README.md](README.md) - Project overview

---

## Quick Reference

```bash
# Start database
docker-compose up -d

# Set connection
export DB_URL=postgresql://postgres@localhost:5435/postgres

# Run all tests
uv run pytest

# Run unit tests only
uv run pytest -m unit

# Run with coverage
uv run pytest --cov=dbsamizdat --cov-report=term-missing

# Stop database
docker-compose down
```

