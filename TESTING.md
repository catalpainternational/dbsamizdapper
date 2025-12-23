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

**Option A: Using Podman (Preferred)**

Podman is preferred if available. Use different ports for different branches to allow parallel testing:

```bash
# Default port (5435) and PostgreSQL version 15 (default)
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15

# Different port for parallel branches (e.g., feature branch)
podman run -d -p 5436:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15

# Using different PostgreSQL version (e.g., version 16)
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:16
```

**Option B: Using Docker**

```bash
# Default port and PostgreSQL version 15 (default)
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15

# Different port for parallel branches
docker run -d -p 5436:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15

# Using different PostgreSQL version (e.g., version 16)
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16
```

**Option C: Using Docker Compose**

```bash
# Default PostgreSQL version 15
# Use 'docker compose' (Docker Compose v2) or 'docker-compose' (standalone)
docker compose up -d
# Or: docker-compose up -d

# Using different PostgreSQL version (e.g., version 16)
POSTGRES_VERSION=16 docker compose up -d
# Or: POSTGRES_VERSION=16 docker-compose up -d
```

**Note**: 
- For parallel branch testing, use different ports (e.g., 5435, 5436, 5437) and configure `DB_PORT` accordingly.
- PostgreSQL version defaults to 15. Set `POSTGRES_VERSION` environment variable to use a different version (e.g., `POSTGRES_VERSION=16`).
- Docker Compose: Use `docker compose` (Docker Compose v2, built into Docker) or `docker-compose` (standalone). Both work with the same `docker-compose.yml` file.

### 2. Set Database Connection

**Option A: Using DB_PORT (Recommended for parallel branches)**

Set the port number as an environment variable:
```bash
export DB_PORT=5435
```

The test suite will automatically construct the connection string: `postgresql://postgres@localhost:5435/postgres`

**Option B: Using Full DB_URL**

Set the complete connection string:
```bash
export DB_URL=postgresql://postgres@localhost:5435/postgres
```

**Option C: Create `.env` File**

Create a `.env` file in the project root:
```bash
# Using port number (preferred for parallel branches)
DB_PORT=5435

# Or using full connection string
# DB_URL=postgresql://postgres@localhost:5435/postgres
```

The test suite automatically loads `.env` files using `python-dotenv`.

**Note**: A `.env.example` file should exist in the repository as a template. If it doesn't, create `.env` with the content above.

### Parallel Branch Testing

To run tests on different branches simultaneously, use different ports:

```bash
# Branch 1 (main) - PostgreSQL 15 (default)
export DB_PORT=5435
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15

# Branch 2 (feature-branch) - PostgreSQL 15 (default)
export DB_PORT=5436
podman run -d -p 5436:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15

# Branch 3 (testing PostgreSQL 16)
export DB_PORT=5437
podman run -d -p 5437:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:16
```

### PostgreSQL Version Configuration

The PostgreSQL version defaults to **15**. You can configure it using:

**For Docker Compose:**
```bash
# Docker Compose v2 (built into Docker)
POSTGRES_VERSION=16 docker compose up -d
# Or standalone docker-compose
POSTGRES_VERSION=16 docker-compose up -d
```

**For Podman/Docker:**
```bash
# Use version 16
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:16

# Use version 14
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:14
```

**Available PostgreSQL versions:** 12, 13, 14, 15, 16 (check [Docker Hub](https://hub.docker.com/_/postgres) for latest versions)

### 3. Run Tests

**Important**: Ensure the database is ready before running tests. Integration tests require a running PostgreSQL database.

```bash
# All tests (requires database)
uv run pytest

# Unit tests only (no database required)
uv run pytest -m unit

# Integration tests only (requires database)
uv run pytest -m integration
```

**Note**: Always use `uv run pytest` (not `pytest` or `python -m pytest`) to ensure dependencies are available in the virtual environment.

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

For parallel branch testing or when port 5435 is already in use:

**Option 1: Using DB_PORT (Recommended)**
```bash
export DB_PORT=5436
```

**Option 2: Using DB_URL**
```bash
export DB_URL=postgresql://postgres@localhost:5436/postgres
```

**Option 3: Update `docker-compose.yml`**
```yaml
ports:
  - "5436:5432"  # Change 5435 to 5436
```
Then set `DB_PORT=5436` or update `DB_URL` accordingly.

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

### `DB_PORT` (Recommended for parallel branches)

Port number for the database connection. The test suite will construct the full connection string automatically.

```bash
export DB_PORT=5435
```

This is particularly useful when running tests on different branches simultaneously, as each branch can use a different port.

**Priority**: If `DB_URL` or `DBURL` is set, `DB_PORT` is ignored.

### `DB_URL` (Primary)

Full database connection string.

```bash
export DB_URL=postgresql://postgres@localhost:5435/postgres
```

### `DBURL` (Alternative)

Alternative name for database URL (for compatibility).

```bash
export DBURL=postgresql://postgres@localhost:5435/postgres
```

**Priority**: `DB_URL` takes precedence over `DBURL`, which takes precedence over `DB_PORT`. If none are set, defaults to port 5435.

### `POSTGRES_VERSION`

PostgreSQL version to use when starting the database container. Defaults to **15**.

```bash
export POSTGRES_VERSION=16
```

This is used by `docker compose` or `docker-compose` to select the PostgreSQL image version. For podman/docker commands, specify the version directly in the image tag (e.g., `postgres:16`).

**Note**: This only affects `docker compose up` or `docker-compose up`. For podman/docker commands, specify the version in the image tag.

### Loading from `.env` File

The test suite automatically loads environment variables from `.env` files using `python-dotenv`.

Create a `.env` file in the project root:
```bash
# Recommended: Use DB_PORT for easy port switching
DB_PORT=5435

# PostgreSQL version (for docker-compose, defaults to 15)
POSTGRES_VERSION=15

# Or use full connection string
# DB_URL=postgresql://postgres@localhost:5435/postgres
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
   docker compose ps
   # Or: docker-compose ps
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
   - Or use `DB_PORT` environment variable

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
   docker compose restart
   # Or: docker-compose restart
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
# Start database (prefer podman if available)
# Default PostgreSQL version 15
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15
# Or use version 16
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:16
# Or with docker compose (defaults to PostgreSQL 15)
docker compose up -d
# Or: docker-compose up -d
# Or with docker compose using version 16
POSTGRES_VERSION=16 docker compose up -d
# Or: POSTGRES_VERSION=16 docker-compose up -d

# Set connection (use DB_PORT for parallel branches)
export DB_PORT=5435
# Or use full connection string
# export DB_URL=postgresql://postgres@localhost:5435/postgres

# Run all tests
uv run pytest

# Run unit tests only
uv run pytest -m unit

# Run with coverage
uv run pytest --cov=dbsamizdat --cov-report=term-missing

# Stop database
podman stop <container-id>
# Or with docker compose
docker compose down
# Or: docker-compose down
```

