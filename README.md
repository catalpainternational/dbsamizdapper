# Dbsamizdapper

The "blissfully naive PostgreSQL database object manager"
This is based on the original `dbsamizdat` code from https://git.sr.ht/~nullenenenen/DBSamizdat/ a version of which was previously hosted at `https://github.com/catalpainternational/dbsamizdat`

Full disclosure: That one (https://git.sr.ht/~nullenenenen/DBSamizdat/ which is also on pypi) is definitely less likely to have bugs, it was written by a better coder than I am, the original author is "nullenenenen <nullenenenen@gavagai.eu>"

## Quick Start

**For detailed usage examples, see [USAGE.md](USAGE.md)**

### Basic Example

1. Create a module with your database views:

```python
# myapp/views.py
from dbsamizdat import SamizdatView

class UserStats(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT COUNT(*) as total_users FROM users
        ${postamble}
    """
```

2. Sync to your database:

```bash
# Using CLI (modules are automatically imported)
python -m dbsamizdat.runner sync postgresql:///mydb myapp.views

# Or using library API
python -c "from dbsamizdat import sync; sync('postgresql:///mydb', samizdatmodules=['myapp.views'])"
```

### Key Points

- **Module Import**: The CLI automatically imports modules you specify - no need to manually import them first
- **Database Connection**: Use `DBURL` environment variable or pass connection string directly
- **Python 3.12+**: Requires Python 3.12 or later
- **PostgreSQL Only**: Works exclusively with PostgreSQL databases
- **Dollar-Quoting**: `$$` does not work in SQL functions - use tags like `$BODY$` instead (see [USAGE.md](USAGE.md#dollar-quoting-in-functions-))

## Installation

### For Users
```bash
pip install dbsamizdapper
```

### For Development

This project uses [UV](https://github.com/astral-sh/uv) for fast dependency management.

**Install UV:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

**Setup development environment:**
```bash
# Clone the repository
git clone <repo-url>
cd dbsamizdapper

# Install dependencies (includes dev tools)
uv sync --group dev --group testing

# Optional: Install Django type stubs for Django integration development
uv sync --group dev --group testing --extra django
```

**Available dependency groups (development):**
- `dev` - Development tools (ruff, mypy, etc.)
- `testing` - Test framework and PostgreSQL testing with psycopg2-binary

**Available extras (optional runtime features):**
- `django` - Django 4.2 and type stubs for Django integration
- `psycopg3` - Use psycopg3 instead of psycopg2

## Quick Test Setup

### Integration Tests (Requires Database)

1. **Start PostgreSQL database:**
   ```bash
   # Prefer podman if available (for parallel branch testing)
   # Default PostgreSQL version 15
   podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15
   # Or with docker:
   docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15
   # Or with docker compose (defaults to PostgreSQL 15):
   docker compose up -d
   # Or: docker-compose up -d
   # Or with docker compose using different version:
   POSTGRES_VERSION=16 docker compose up -d
   # Or: POSTGRES_VERSION=16 docker-compose up -d
   ```

2. **Set database connection:**
   ```bash
   # Recommended: Use DB_PORT for easy port switching (useful for parallel branches)
   export DB_PORT=5435
   # Or use full connection string:
   # export DB_URL=postgresql://postgres@localhost:5435/postgres
   # Or create .env file (copy .env.example and adjust if needed)
   ```

3. **Run all tests:**
   ```bash
   uv run pytest
   ```

### Unit Tests Only (No Database Required)

```bash
uv run pytest -m unit
```

### Troubleshooting

- **Connection refused**: Make sure PostgreSQL is running on port 5435
- **Authentication failed**: Check `DB_URL` format: `postgresql://user@host:port/dbname`
- **Port in use**: Change port mapping in `docker-compose.yml` or use different port in `DB_URL` or set `DB_PORT`

See [TESTING.md](TESTING.md) for detailed testing guide.

## New features

This fork is based on a rewrite which I did to better understand the internals of `dbsamizdat` as we use it in a few different projects. The changes include:

 - Python 3.12+
 - Type hints throughout the codebase
 - Changed from `ABC` to `Protocol` type for inheritance
 - UV for fast dependency management
 - **Table Management** (new in 0.0.6)
   - `SamizdatTable` - Manage database tables as Samizdat objects
   - UNLOGGED table support for performance-critical use cases
 - **Django QuerySet integration** (0.0.5)
   - `SamizdatQuerySet` - Create views from Django QuerySets
   - `SamizdatMaterializedQuerySet` - Materialized views from QuerySets
   - `SamizdatModel` - Unmanaged Django models as views
   - `SamizdatMaterializedModel` - Materialized views from models
 - Compat with both `psycopg` and `psycopg3`
 - Opinionated code formatting
   - black + isort
   - replaced `lambda`s
 - some simple `pytest` functions

and probably many more undocumented changes

### Table Management Example

```python
from dbsamizdat import SamizdatTable

class MyTable(SamizdatTable):
    """Manage a table as a Samizdat object"""
    sql_template = """
    CREATE TABLE ${samizdatname} (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """

class MyCacheTable(SamizdatTable):
    """UNLOGGED table for better performance"""
    unlogged = True
    sql_template = """
    CREATE TABLE ${samizdatname} (
        key TEXT PRIMARY KEY,
        value JSONB,
        expires_at TIMESTAMP
    )
    """
```

### Django QuerySet Example

```python
from dbsamizdat import SamizdatMaterializedQuerySet
from myapp.models import MyModel

class MyComplexView(SamizdatMaterializedQuerySet):
    """Create a materialized view from a complex QuerySet"""
    queryset = MyModel.objects.select_related('related').filter(
        active=True
    ).annotate(
        custom_field=F('field1') + F('field2')
    )

    # Optionally specify tables that trigger refresh
    refresh_triggers = [("myapp", "mymodel")]
```


## Development Commands

**Run tests:**
```bash
# Ensure database is ready first (see TESTING.md for setup)
uv run pytest
```

**Note**: Always use `uv run pytest` (not `pytest` or `python -m pytest`) to ensure dependencies are available in the virtual environment.

**Linting and formatting:**
```bash
uv run ruff check .
uv run ruff format .
uv run mypy dbsamizdat
```

**Pre-commit hooks:**
This project uses [pre-commit](https://pre-commit.com/) for automated code quality checks. Install it using [uv](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/):

```bash
# Install pre-commit with uv (recommended method)
uv tool install pre-commit --with pre-commit-uv

# Install Git hooks (runs automatically on commit)
pre-commit install

# Run on all files manually
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run a specific hook
pre-commit run ruff --all-files

# Update pre-commit hooks to latest versions
pre-commit autoupdate

# Upgrade pre-commit itself
uv tool upgrade pre-commit
```

**Note:** Pre-commit hooks will automatically run when you commit. To skip hooks (not recommended), use `git commit --no-verify`.

**Build package:**
```bash
uv build
```

## Running Tests

> **Quick Start**: See [Quick Test Setup](#quick-test-setup) above for the fastest way to run tests.

### Detailed Setup

**Start PostgreSQL database:**

Prefer podman if available (useful for parallel branch testing):
```bash
# Default PostgreSQL version 15
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:15
# Or use version 16
podman run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:16
```

Or with Docker:
```bash
# Default PostgreSQL version 15
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15
# Or use version 16
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16
```

Or with docker compose:
```bash
# Default PostgreSQL version 15
docker compose up -d
# Or: docker-compose up -d
# Or use version 16
POSTGRES_VERSION=16 docker compose up -d
# Or: POSTGRES_VERSION=16 docker-compose up -d
```

**Set database connection:**

**Option 1: Using DB_PORT (Recommended for parallel branches)**
```bash
export DB_PORT=5435
```

**Option 2: Using full connection string**
```bash
export DB_URL=postgresql://postgres@localhost:5435/postgres
```

**Option 3: Create `.env` file**
Create a `.env` file in the project root (copy from `.env.example` if available):
```
DB_PORT=5435
POSTGRES_VERSION=15
# Or: DB_URL=postgresql://postgres@localhost:5435/postgres
```

The test suite will automatically load `.env` files using `python-dotenv`.

**Note**: 
- For parallel branch testing, use different ports (e.g., 5435, 5436, 5437) and set `DB_PORT` accordingly.
- PostgreSQL version defaults to 15. Set `POSTGRES_VERSION` to use a different version (for `docker compose` or `docker-compose`) or specify the version in the image tag (for podman/docker).
- Docker Compose: Use `docker compose` (Docker Compose v2, built into Docker) or `docker-compose` (standalone). Both work with the same `docker-compose.yml` file.

**Run tests:**
```bash
# All tests (requires database)
uv run pytest

# Unit tests only (no database required)
uv run pytest -m unit

# Integration tests only (requires database)
uv run pytest -m integration
```

## Documentation

- **[USAGE.md](USAGE.md)** - Comprehensive usage guide with examples for:
  - Non-Django projects
  - Django integration
  - Library API usage
  - Common patterns and troubleshooting

## Original README

Check out [README.original.md](README.original.md) for the original rationale and advanced features

## Publishing

 - bump the version number in `pyproject.toml`
 - tag a release on github
 - `uv build`
 - `uv publish`
   - username: __token__
   - token: (get it from pypi)
