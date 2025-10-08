# Dbsamizdapper

The "blissfully naive PostgreSQL database object manager"
This is based on the original `dbsamizdat` code from https://git.sr.ht/~nullenenenen/DBSamizdat/ a version of which was previously hosted at `https://github.com/catalpainternational/dbsamizdat`

Full disclosure: That one (https://git.sr.ht/~nullenenenen/DBSamizdat/ which is also on pypi) is definitely less likely to have bugs, it was written by a better coder than I am, the original author is "nullenenenen <nullenenenen@gavagai.eu>"

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
uv sync --extra dev --extra testing

# Optional: Install Django type stubs for Django integration development
uv sync --extra dev --extra testing --extra django
```

**Available extras:**
- `dev` - Development tools (black, isort, flake8, mypy, pytest, etc.)
- `testing` - PostgreSQL testing with psycopg2-binary
- `django` - Django 4.2 and type stubs for Django integration
- `psycopg3` - Use psycopg3 instead of psycopg2

## New features

This fork is based on a rewrite which I did to better understand the internals of `dbsamizdat` as we use it in a few different projects. The changes include:

 - Python 3.12+
 - Type hints throughout the codebase
 - Changed from `ABC` to `Protocol` type for inheritance
 - UV for fast dependency management
 - **Django QuerySet integration** (new in 0.0.5)
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
uv run pytest
```

**Linting and formatting:**
```bash
uv run black .
uv run isort .
uv run flake8 .
uv run mypy dbsamizdat
```

**Build package:**
```bash
uv build
```

## Running Tests

Spin up a docker container

`docker run -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:latest`

The db url for this container would be:

"postgresql:///postgres@localhost:5435/postgres"

Make this the environment variable `DB_URL`, or add it to the `.env` file

## Original README

Check out the original readme for rationale and how-to documentation


