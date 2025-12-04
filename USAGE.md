# Dbsamizdapper Usage Guide

This guide provides clear examples for using dbsamizdapper in your projects, both with and without Django.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Non-Django Usage](#non-django-usage)
3. [Django Integration](#django-integration)
4. [Library API](#library-api)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

## Quick Start

### Installation

```bash
pip install dbsamizdapper
```

### Basic Example

Create a module with your database views:

```python
# myapp/views.py
from dbsamizdat import SamizdatView, SamizdatMaterializedView

class UserStats(SamizdatView):
    """A simple view showing user statistics"""
    sql_template = """
        ${preamble}
        SELECT
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE is_active) as active_users
        FROM users
        ${postamble}
    """

class UserStatsCached(SamizdatMaterializedView):
    """Materialized view for faster queries"""
    deps_on = {UserStats}
    sql_template = """
        ${preamble}
        SELECT * FROM "UserStats"
        WHERE total_users > 100
        ${postamble}
    """
```

Sync to your database:

```bash
# Using CLI
python -m dbsamizdat.runner sync postgresql:///mydb myapp.views

# Or using library API
python -c "from dbsamizdat import sync; sync('postgresql:///mydb', samizdatmodules=['myapp.views'])"
```

## Non-Django Usage

### Project Structure

```
myproject/
├── myapp/
│   ├── __init__.py
│   ├── views.py          # Your samizdat definitions
│   └── models.py         # More samizdat definitions
├── requirements.txt
└── README.md
```

### Defining Samizdats

Create modules containing your samizdat classes:

```python
# myapp/views.py
from dbsamizdat import SamizdatView, SamizdatMaterializedView, SamizdatTable

# Define a table
class CacheTable(SamizdatTable):
    """Unlogged table for caching"""
    unlogged = True
    sql_template = """
        ${preamble}
        (
            key TEXT PRIMARY KEY,
            value JSONB,
            expires_at TIMESTAMP
        )
        ${postamble}
    """

# Define a view
class ActiveUsers(SamizdatView):
    """View of active users"""
    sql_template = """
        ${preamble}
        SELECT id, username, email
        FROM users
        WHERE is_active = true
        ${postamble}
    """

# Define a materialized view with dependencies
class UserActivity(SamizdatMaterializedView):
    """Materialized view showing user activity"""
    deps_on = {ActiveUsers}
    deps_on_unmanaged = {"orders"}  # Reference to unmanaged table
    sql_template = """
        ${preamble}
        SELECT
            u.id,
            u.username,
            COUNT(o.id) as order_count
        FROM "ActiveUsers" u
        LEFT JOIN orders o ON o.user_id = u.id
        GROUP BY u.id, u.username
        ${postamble}
    """
    # Optional: auto-refresh when base tables change
    refresh_triggers = [("public", "orders")]
```

### Using the CLI

The CLI requires module names as arguments. These modules will be imported automatically:

```bash
# Sync all samizdats from specified modules
python -m dbsamizdat.runner sync postgresql:///mydb myapp.views myapp.models

# Refresh materialized views
python -m dbsamizdat.runner refresh postgresql:///mydb myapp.views

# Show differences between code and database
python -m dbsamizdat.runner diff postgresql:///mydb myapp.views

# Drop all samizdat objects
python -m dbsamizdat.runner nuke postgresql:///mydb myapp.views

# Generate dependency graph
python -m dbsamizdat.runner printdot myapp.views | dot -Tpng > graph.png
```

### Using Environment Variables

Set `DBURL` environment variable to avoid passing connection string each time:

```bash
export DBURL="postgresql://user:password@localhost:5432/mydb"
python -m dbsamizdat.runner sync myapp.views
```

Or use a `.env` file:

```bash
# .env
DBURL=postgresql://user:password@localhost:5432/mydb
```

### Using the Library API

```python
from dbsamizdat import sync, refresh, nuke

# Sync samizdats from specific modules
sync(
    dburl="postgresql:///mydb",
    samizdatmodules=["myapp.views", "myapp.models"]
)

# Refresh materialized views
refresh(
    dburl="postgresql:///mydb",
    samizdatmodules=["myapp.views"],
    belownodes=["orders"]  # Only refresh views depending on orders table
)

# Remove all samizdat objects
nuke(
    dburl="postgresql:///mydb",
    samizdatmodules=["myapp.views"]
)
```

### Programmatic Usage with Explicit Classes

You can also pass samizdat classes directly:

```python
from dbsamizdat.runner import cmd_sync, ArgType
from myapp.views import ActiveUsers, UserActivity

args = ArgType(
    dburl="postgresql:///mydb",
    txdiscipline="jumbo",
    verbosity=1
)

# Pass explicit classes
cmd_sync(args, samizdatsIn=[ActiveUsers, UserActivity])
```

## Django Integration

### Setup

1. Add `dbsamizdat` to `INSTALLED_APPS`:

```python
# settings.py
INSTALLED_APPS = [
    # ... other apps
    'dbsamizdat',
    'myapp',
]
```

2. Create `dbsamizdat_defs.py` in your Django apps:

```python
# myapp/dbsamizdat_defs.py
from dbsamizdat import SamizdatView, SamizdatMaterializedView
from myapp.models import User, Order

class UserStats(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE is_active) as active_users
        FROM myapp_user
        ${postamble}
    """
```

### Using Django Management Command

```bash
# Sync all samizdats (auto-discovered from dbsamizdat_defs.py files)
./manage.py dbsamizdat sync

# Refresh materialized views
./manage.py dbsamizdat refresh

# Show differences
./manage.py dbsamizdat diff

# Drop all samizdat objects
./manage.py dbsamizdat nuke
```

### Django QuerySet Integration

Create views from Django QuerySets:

```python
# myapp/dbsamizdat_defs.py
from dbsamizdat import SamizdatQuerySet, SamizdatMaterializedQuerySet
from myapp.models import User, Order

class ActiveUsersView(SamizdatQuerySet):
    """View from Django QuerySet"""
    queryset = User.objects.filter(is_active=True).select_related('profile')

class UserOrderStats(SamizdatMaterializedQuerySet):
    """Materialized view from QuerySet"""
    queryset = (
        User.objects
        .filter(is_active=True)
        .annotate(order_count=Count('orders'))
        .values('id', 'username', 'order_count')
    )
    # Auto-refresh when orders table changes
    refresh_triggers = [("myapp", "order")]
```

### Django Model Integration

Create unmanaged Django models as views:

```python
# myapp/dbsamizdat_defs.py
from dbsamizdat import SamizdatModel, SamizdatMaterializedModel
from django.db import models

class UserStatsModel(SamizdatModel):
    """Unmanaged Django model representing a view"""
    total_users = models.IntegerField()
    active_users = models.IntegerField()

    class Meta:
        managed = False  # Don't create table, use view instead
        db_table = 'user_stats_view'

    sql_template = """
        ${preamble}
        SELECT
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE is_active) as active_users
        FROM myapp_user
        ${postamble}
    """
```

## Common Patterns

### Dependency Management

```python
class BaseView(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT 1 as value
        ${postamble}
    """

class DependentView(SamizdatView):
    # Explicit dependency
    deps_on = {BaseView}
    sql_template = """
        ${preamble}
        SELECT * FROM "BaseView"
        ${postamble}
    """

class AnotherView(SamizdatView):
    # Reference unmanaged database objects
    deps_on_unmanaged = {"public", "orders"}
    sql_template = """
        ${preamble}
        SELECT * FROM orders
        ${postamble}
    """
```

### Schema Management

```python
class CustomSchemaView(SamizdatView):
    schema = "analytics"  # Use custom schema
    sql_template = """
        ${preamble}
        SELECT now() as timestamp
        ${postamble}
    """
```

### Custom Names

```python
class MyView(SamizdatView):
    object_name = "custom_view_name"  # Override default class name
    sql_template = """
        ${preamble}
        SELECT 1
        ${postamble}
    """
```

### Functions and Triggers

**Important**: PostgreSQL's `$$` dollar-quoting syntax does **not** work in SQL templates because it clashes with Python's `string.Template` processing. Use a tag like `$BODY$` instead.

```python
from dbsamizdat import SamizdatFunction, SamizdatTrigger

class MyFunction(SamizdatFunction):
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN UPPER(input);
        END;
        $BODY$
        LANGUAGE plpgsql;
    """

class MyTrigger(SamizdatTrigger):
    deps_on = {MyFunction}
    sql_template = """
        CREATE TRIGGER ${samizdatname}
        AFTER INSERT ON my_table
        FOR EACH ROW
        EXECUTE FUNCTION ${samizdatname}('triggered');
    """
```

## Troubleshooting

### Dollar-Quoting in Functions (`$$`)

**Problem**: Using `$$` for dollar-quoted strings in PostgreSQL functions causes template errors.

**Explanation**: Dbsamizdapper uses Python's `string.Template` to process SQL templates. In Python templates, `$$` is interpreted as an escaped `$` character, which conflicts with PostgreSQL's `$$` dollar-quoting syntax.

**Solution**: Use a tag instead of `$$`. Any tag works (e.g., `$BODY$`, `$FUNC$`, `$CODE$`):

```python
# ❌ This will NOT work
class BadFunction(SamizdatFunction):
    sql_template = """
        ${preamble}
        RETURNS TEXT AS $$
        SELECT 'test';
        $$ LANGUAGE SQL;
    """

# ✅ Use a tag instead
class GoodFunction(SamizdatFunction):
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'test';
        $BODY$
        LANGUAGE SQL;
    """
```

### Module Not Found Errors

**Problem**: `ModuleNotFoundError: No module named 'myapp.views'`

**Solution**: Ensure your module is on Python path or use absolute imports:

```bash
# Add current directory to PYTHONPATH
PYTHONPATH=. python -m dbsamizdat.runner sync postgresql:///mydb myapp.views

# Or install your package in development mode
pip install -e .
```

### Database Connection Issues

**Problem**: Connection string errors

**Solution**: Use proper PostgreSQL connection string format:

```python
# Local database
"postgresql:///database_name"

# With user
"postgresql://user@localhost/database_name"

# Full connection string
"postgresql://user:password@host:port/database_name"
```

### Circular Dependencies

**Problem**: `DependencyCycleError`

**Solution**: Review your dependency graph:

```bash
python -m dbsamizdat.runner printdot myapp.views | dot -Tpng > graph.png
```

### Views Not Updating

**Problem**: Materialized views not refreshing

**Solution**:
- Use `refresh()` command or API
- Check `refresh_triggers` configuration
- Verify triggers were created: `\d+ view_name` in psql

### Django Integration Issues

**Problem**: Samizdats not discovered in Django

**Solution**:
- Ensure `dbsamizdat` is in `INSTALLED_APPS`
- Create `dbsamizdat_defs.py` in your app directory
- Check that app is in `INSTALLED_APPS`
- Use `DBSAMIZDAT_MODULES` setting for custom module locations:

```python
# settings.py
DBSAMIZDAT_MODULES = [
    "myapp.custom_views",
    "shared.analytics",
]
```

## Additional Resources

- See `README.md` for installation and development setup
- See `README.original.md` for original rationale and advanced features
- See `DEVELOPMENT.md` for development setup and pre-commit usage
- Check test files in `tests/` for more examples
- [Pre-commit installation guide with uv](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/) - Recommended way to install pre-commit for development

## Development Tools

### Pre-commit Hooks

This project uses pre-commit to ensure code quality. After installing pre-commit:

```bash
# Install pre-commit with uv (recommended)
uv tool install pre-commit --with pre-commit-uv

# Install Git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run on staged files (default on commit)
pre-commit run
```

Pre-commit will automatically:
- Format code with ruff
- Check linting with ruff
- Run type checking with mypy
- Check for common issues (trailing whitespace, large files, etc.)

See `DEVELOPMENT.md` for complete pre-commit documentation.
