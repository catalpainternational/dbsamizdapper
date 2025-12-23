# Dbsamizdapper Usage Guide

This guide provides clear examples for using dbsamizdapper in your projects, both with and without Django.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Non-Django Usage](#non-django-usage)
3. [Django Integration](#django-integration)
4. [Library API](#library-api)
5. [Common Patterns](#common-patterns)
6. [Best Practices and Common Patterns](#best-practices-and-common-patterns)
7. [Template Variables Reference](#template-variables-reference)
8. [Troubleshooting](#troubleshooting)

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

> **Note**: For a complete reference of template variables (`${preamble}`, `${postamble}`, `${samizdatname}`) and what they're replaced with, see [Template Variables Reference](#template-variables-reference).

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

#### Function Signature Handling

When creating `SamizdatFunction` classes, you need to understand how `function_arguments_signature` and `sql_template` interact. There are two valid approaches:

**Option A: Full CREATE FUNCTION in template** (Less common)

Include the complete `CREATE FUNCTION` statement in your `sql_template` and set `function_arguments_signature = ""`:

```python
class MyFunction(SamizdatFunction):
    function_arguments_signature = ""  # Empty when using full CREATE FUNCTION
    sql_template = f"""
        CREATE FUNCTION {MyFunction.db_object_identity()}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN 'Hello';
        END;
        $BODY$
        LANGUAGE plpgsql;
    """
```

**Option B: Use `${preamble}` (Recommended)**

Omit `CREATE FUNCTION` from your template and use `${preamble}`, which automatically includes `CREATE FUNCTION {schema}.{name}({signature})`. Set `function_arguments_signature` to your parameter signature:

> **See also**: [Template Variables Reference](#template-variables-reference) for complete details on `${preamble}` and other template variables.

```python
class MyFunction(SamizdatFunction):
    function_arguments_signature = "name TEXT"  # Parameter signature
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN UPPER(name);
        END;
        $BODY$
        LANGUAGE plpgsql;
    """
```

**Important Behavior:**

- `creation_identity()` always includes parentheses: `"schema"."name"({args})`
- Even when `function_arguments_signature = ""`, it becomes `"schema"."name"()`
- If you include `CREATE FUNCTION` in your template AND use `${preamble}`, you'll get signature duplication errors like `CREATE FUNCTION name(sig)(sig)` - avoid this!

#### Function Examples

**Function with no parameters:**

```python
class SimpleFunction(SamizdatFunction):
    function_arguments_signature = ""  # No parameters
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'Hello, World!';
        $BODY$
        LANGUAGE SQL;
    """
```

**Function with parameters:**

```python
class GreetFunction(SamizdatFunction):
    function_arguments_signature = "name TEXT, age INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN format('Hello %s, you are %s years old', name, age);
        END;
        $BODY$
        LANGUAGE plpgsql;
    """
```

**Function returning a table:**

```python
class UserStatsFunction(SamizdatFunction):
    function_arguments_signature = "user_id INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TABLE(
            total_orders INTEGER,
            total_spent NUMERIC,
            last_order_date TIMESTAMP
        ) AS
        $BODY$
        BEGIN
            RETURN QUERY
            SELECT
                COUNT(*)::INTEGER,
                COALESCE(SUM(amount), 0),
                MAX(order_date)
            FROM orders
            WHERE user_id = user_id;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """
```

**Function with function polymorphism (same name, different signatures):**

```python
class GetUser(SamizdatFunction):
    function_name = "get_user"  # Shared function name
    function_arguments_signature = "user_id INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TABLE(id INTEGER, name TEXT) AS
        $BODY$
        SELECT id, name FROM users WHERE id = user_id;
        $BODY$
        LANGUAGE SQL;
    """

class GetUserByName(SamizdatFunction):
    function_name = "get_user"  # Same name, different signature
    function_arguments_signature = "username TEXT"
    sql_template = """
        ${preamble}
        RETURNS TABLE(id INTEGER, name TEXT) AS
        $BODY$
        SELECT id, name FROM users WHERE name = username;
        $BODY$
        LANGUAGE SQL;
    """
```

#### Triggers

```python
from dbsamizdat import SamizdatTrigger

class MyTrigger(SamizdatTrigger):
    deps_on = {MyFunction}
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE FUNCTION {MyFunction.creation_identity()};
    """
```

**Important**: When referencing a function in a trigger template, you cannot use template variables. Use Python f-string interpolation with the function class's `creation_identity()` method instead. See [Template Variables Reference](#template-variables-reference) for details.

## Best Practices and Common Patterns

This section provides actionable checklists and common patterns to help you implement functions and triggers correctly without trial-and-error.

### Function Creation Checklist

When creating a `SamizdatFunction`, follow this checklist:

- [ ] **Decide**: Include `CREATE FUNCTION` in template OR use `function_arguments_signature`
  - **Option A**: Include full `CREATE FUNCTION` statement → Set `function_arguments_signature = ""`
  - **Option B** (Recommended): Use `${preamble}` → Set `function_arguments_signature` to your parameter signature
- [ ] **If including in template**: Set `function_arguments_signature = ""`
- [ ] **Use `${samizdatname}` placeholder** (not hardcoded name) when referencing the function within its own body
- [ ] **Use `$BODY$` or `$FUNC$` for dollar-quoting** (not `$$`) - PostgreSQL's `$$` conflicts with Python's template processing

### Trigger Creation Checklist

When creating a `SamizdatTrigger`, follow this checklist:

- [ ] **Start template with `${preamble}`** - This provides the `CREATE TRIGGER` statement with proper table reference
- [ ] **Use `FunctionClass.creation_identity()` for function references** - Use Python f-string interpolation, not template variables
- [ ] **Include function class in `deps_on` set** - This ensures proper dependency ordering
- [ ] **Verify `on_table` format** - Can be a string, tuple `(schema, table)`, or Django model class

### Common Patterns

Here are complete, working examples for common use cases:

#### Pattern 1: Simple Function (No Parameters)

```python
from dbsamizdat import SamizdatFunction

class SimpleFunction(SamizdatFunction):
    """Function with no parameters"""
    function_arguments_signature = ""  # No parameters
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'Hello, World!';
        $BODY$
        LANGUAGE SQL;
    """
```

**Key points:**
- `function_arguments_signature = ""` for no parameters
- Uses `${preamble}` which generates `CREATE FUNCTION "schema"."name"()`
- Uses `$BODY$` instead of `$$` for dollar-quoting

#### Pattern 2: Function with Parameters

```python
from dbsamizdat import SamizdatFunction

class GreetFunction(SamizdatFunction):
    """Function with parameters"""
    function_arguments_signature = "name TEXT, age INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN format('Hello %s, you are %s years old', name, age);
        END;
        $BODY$
        LANGUAGE plpgsql;
    """
```

**Key points:**
- `function_arguments_signature` contains parameter signature without parentheses
- `${preamble}` automatically includes the signature: `CREATE FUNCTION "schema"."name"(name TEXT, age INTEGER)`
- Parameters are used directly in the function body

#### Pattern 3: Trigger Calling Function

```python
from dbsamizdat import SamizdatFunction, SamizdatTrigger, SamizdatTable

class MyTable(SamizdatTable):
    """Table for trigger example"""
    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """

class UpdateTimestampFunction(SamizdatFunction):
    """Function that updates timestamp"""
    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TRIGGER AS
        $BODY$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """

class UpdateTimestampTrigger(SamizdatTrigger):
    """Trigger that calls the update timestamp function"""
    on_table = MyTable  # Can be class, tuple, or string
    condition = "BEFORE UPDATE"
    deps_on = {UpdateTimestampFunction}  # Include function in dependencies
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE FUNCTION {UpdateTimestampFunction.creation_identity()};
    """
```

**Key points:**
- Trigger starts with `${preamble}` (use double braces `{{` in f-strings)
- Function reference uses `FunctionClass.creation_identity()` with f-string interpolation
- Function class included in `deps_on` set
- `on_table` can be a class reference, tuple `("schema", "table")`, or string

#### Pattern 4: Multi-Function Dependencies

```python
from dbsamizdat import SamizdatFunction, SamizdatTrigger, SamizdatTable

class MyTable(SamizdatTable):
    """Table for multi-function example"""
    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """

class ValidateNameFunction(SamizdatFunction):
    """Function to validate name"""
    function_arguments_signature = "name_value TEXT"
    sql_template = """
        ${preamble}
        RETURNS BOOLEAN AS
        $BODY$
        BEGIN
            RETURN length(name_value) > 0 AND length(name_value) <= 100;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """

class LogChangeFunction(SamizdatFunction):
    """Function to log changes"""
    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TRIGGER AS
        $BODY$
        BEGIN
            -- Log the change (simplified example)
            RAISE NOTICE 'Change logged for record %', NEW.id;
            RETURN NEW;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """

class ValidateAndLogTrigger(SamizdatTrigger):
    """Trigger that uses multiple functions"""
    on_table = MyTable
    condition = "BEFORE INSERT OR UPDATE"
    deps_on = {ValidateNameFunction, LogChangeFunction}  # Multiple function dependencies
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW
        WHEN ({ValidateNameFunction.creation_identity()}(NEW.name))
        EXECUTE FUNCTION {LogChangeFunction.creation_identity()};
    """
```

**Key points:**
- Multiple functions can be included in `deps_on` set
- Each function reference uses its own `creation_identity()` method
- Functions can be used in trigger conditions (`WHEN` clause) and execution
- All dependent functions are automatically created before the trigger

### Quick Reference: Common Mistakes to Avoid

❌ **Don't use `$$` for dollar-quoting** - Use `$BODY$` or `$FUNC$` instead
```python
# ❌ Wrong
sql_template = """
    ${preamble}
    RETURNS TEXT AS $$
    SELECT 'test';
    $$ LANGUAGE SQL;
"""

# ✅ Correct
sql_template = """
    ${preamble}
    RETURNS TEXT AS $BODY$
    SELECT 'test';
    $BODY$ LANGUAGE SQL;
"""
```

❌ **Don't hardcode function names** - Use `${samizdatname}` or `creation_identity()`
```python
# ❌ Wrong
sql_template = """
    ${preamble}
    RETURNS TEXT AS $BODY$
    SELECT 'Function: MyFunction';
    $BODY$ LANGUAGE SQL;
"""

# ✅ Correct
sql_template = """
    ${preamble}
    RETURNS TEXT AS $BODY$
    SELECT format('Function: %s', ${samizdatname});
    $BODY$ LANGUAGE SQL;
"""
```

❌ **Don't use template variables for function references in triggers** - Use f-strings with `creation_identity()`
```python
# ❌ Wrong
class MyTrigger(SamizdatTrigger):
    deps_on = {MyFunction}
    sql_template = """
        ${preamble}
        FOR EACH ROW EXECUTE FUNCTION ${function_ref};  # Template variable doesn't exist!
    """

# ✅ Correct
class MyTrigger(SamizdatTrigger):
    deps_on = {MyFunction}
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE FUNCTION {MyFunction.creation_identity()};
    """
```

## Template Variables Reference

Dbsamizdapper uses Python's `string.Template` to process SQL templates. Template variables are replaced with specific SQL strings based on the entity type. This section provides a complete reference of all available template variables and their exact replacements.

### Available Template Variables by Entity Type

#### Views, Tables, and Materialized Views

For `SamizdatView`, `SamizdatTable`, and `SamizdatMaterializedView`:

**`${preamble}`**
- **Replaced with**: `CREATE [UNLOGGED] VIEW/TABLE/MATERIALIZED VIEW "schema"."name" AS`
- **Details**:
  - For views: `CREATE VIEW "schema"."name" AS`
  - For tables: `CREATE TABLE "schema"."name"` (no `AS` keyword)
  - For UNLOGGED tables: `CREATE UNLOGGED TABLE "schema"."name"`
  - For materialized views: `CREATE MATERIALIZED VIEW "schema"."name" AS`
- **Example**:
  ```python
  class MyView(SamizdatView):
      sql_template = """
          ${preamble}
          SELECT 1 as value
          ${postamble}
      """
  # Generates: CREATE VIEW "public"."MyView" AS SELECT 1 as value
  ```

**`${postamble}`**
- **Replaced with**: 
  - For materialized views: `WITH NO DATA`
  - For views and tables: empty string (removed from output)
- **Details**: Only materialized views need `WITH NO DATA` to prevent immediate data population
- **Example**:
  ```python
  class MyMatView(SamizdatMaterializedView):
      sql_template = """
          ${preamble}
          AS SELECT 1 as value
          ${postamble}
      """
  # Generates: CREATE MATERIALIZED VIEW "public"."MyMatView" AS SELECT 1 as value WITH NO DATA
  ```

**`${samizdatname}`**
- **Replaced with**: `"schema"."name"` (the `db_object_identity()` format)
- **Details**: Fully qualified database object name, useful for self-references or cross-references
- **Example**:
  ```python
  class MyView(SamizdatView):
      sql_template = """
          ${preamble}
          SELECT * FROM ${samizdatname}
          ${postamble}
      """
  # Generates: CREATE VIEW "public"."MyView" AS SELECT * FROM "public"."MyView"
  ```

#### Functions

For `SamizdatFunction`:

**`${preamble}`**
- **Replaced with**: `CREATE FUNCTION "schema"."name"({signature})`
- **Details**:
  - Always includes the function signature in parentheses
  - For functions with no parameters: `"schema"."name"()`
  - For functions with parameters: `"schema"."name"(param1 TYPE1, param2 TYPE2)`
  - Uses `creation_identity()` format which includes the signature
- **Example**:
  ```python
  class MyFunction(SamizdatFunction):
      function_arguments_signature = "name TEXT"
      sql_template = """
          ${preamble}
          RETURNS TEXT AS
          $BODY$
          SELECT UPPER(name);
          $BODY$
          LANGUAGE SQL;
      """
  # Generates: CREATE FUNCTION "public"."MyFunction"(name TEXT) RETURNS TEXT AS ...
  ```

**`${samizdatname}`**
- **Replaced with**: `"schema"."name"({signature})` (the `db_object_identity()` format)
- **Details**: Same as `${preamble}` but without the `CREATE FUNCTION` prefix. Includes signature in parentheses.
- **Example**:
  ```python
  class MyFunction(SamizdatFunction):
      function_arguments_signature = ""
      sql_template = """
          ${preamble}
          RETURNS TEXT AS
          $BODY$
          SELECT 'Function: ${samizdatname}';
          $BODY$
          LANGUAGE SQL;
      """
  # Inside the function body, ${samizdatname} becomes "public"."MyFunction"()
  ```

#### Triggers

For `SamizdatTrigger`:

**`${preamble}`**
- **Replaced with**: `CREATE TRIGGER "trigger_name" {condition} ON "schema"."table_name"`
- **Details**:
  - Trigger name is quoted
  - Includes the trigger condition (e.g., `AFTER INSERT`, `BEFORE UPDATE`)
  - Includes the target table's fully qualified identity
  - Does NOT include `FOR EACH ROW` or `EXECUTE FUNCTION` - these must be in your template
- **Example**:
  ```python
  class MyTrigger(SamizdatTrigger):
      on_table = MyTable
      condition = "AFTER INSERT"
      sql_template = """
          ${preamble}
          FOR EACH ROW EXECUTE FUNCTION my_function();
      """
  # Generates: CREATE TRIGGER "MyTrigger" AFTER INSERT ON "public"."MyTable"
  #           FOR EACH ROW EXECUTE FUNCTION my_function();
  ```

**`${samizdatname}`**
- **Replaced with**: `trigger_name` (just the trigger name, **not** quoted, **not** fully qualified)
- **Details**: 
  - Unlike other entity types, this is just the plain trigger name
  - Useful for self-referencing the trigger name in the template
  - **Cannot be used to reference functions** - see "Referencing Functions in Triggers" below
- **Example**:
  ```python
  class MyTrigger(SamizdatTrigger):
      sql_template = """
          ${preamble}
          FOR EACH ROW EXECUTE FUNCTION ${samizdatname}();
      """
  # ${samizdatname} becomes: MyTrigger
  # Full SQL: CREATE TRIGGER "MyTrigger" ... FOR EACH ROW EXECUTE FUNCTION MyTrigger();
  ```

### Referencing Functions in Triggers

**Important**: When you need to reference a function in a trigger template, you **cannot** use template variables. Template variables are only available for the current entity being created.

**❌ Wrong Approach**:
```python
class MyTrigger(SamizdatTrigger):
    deps_on = {MyFunction}
    sql_template = """
        ${preamble}
        FOR EACH ROW EXECUTE FUNCTION ${function_identity}();  # This doesn't exist!
    """
```

**✅ Correct Approach**:
Use Python f-string interpolation with the function class's `creation_identity()` method:

```python
class MyTrigger(SamizdatTrigger):
    deps_on = {MyFunction}
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE FUNCTION {MyFunction.creation_identity()};
    """
```

**Why this works**:
- `creation_identity()` returns the full function identity with signature: `"schema"."name"({args})`
- F-strings evaluate the Python expression at class definition time
- Use double braces `{{` and `}}` to escape template variables in f-strings

**Complete Example**:
```python
class RefreshFunction(SamizdatFunction):
    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TRIGGER AS
        $BODY$
        BEGIN
            REFRESH MATERIALIZED VIEW my_matview;
            RETURN NULL;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """

class RefreshTrigger(SamizdatTrigger):
    on_table = MyTable
    condition = "AFTER INSERT OR UPDATE"
    deps_on = {RefreshFunction}
    sql_template = f"""
        ${{preamble}}
        FOR EACH STATEMENT EXECUTE FUNCTION {RefreshFunction.creation_identity()};
    """
```

### Edge Cases and Notes

**Undefined Variables**: If you use a template variable that doesn't exist (e.g., `${undefined_var}`), Python's `safe_substitute()` will leave it unchanged in the output. This can help catch typos but may also lead to confusing SQL errors.

**Using Template Variables in F-strings**: When using f-strings for your `sql_template`, escape template variables with double braces:
```python
class MyView(SamizdatView):
    sql_template = f"""
        ${{preamble}}
        SELECT 1 as value
        ${{postamble}}
    """
```

**Template Variable Summary Table**:

| Entity Type | `${preamble}` | `${postamble}` | `${samizdatname}` |
|------------|---------------|----------------|-------------------|
| View | `CREATE VIEW "schema"."name" AS` | (empty) | `"schema"."name"` |
| Table | `CREATE TABLE "schema"."name"` | (empty) | `"schema"."name"` |
| UNLOGGED Table | `CREATE UNLOGGED TABLE "schema"."name"` | (empty) | `"schema"."name"` |
| Materialized View | `CREATE MATERIALIZED VIEW "schema"."name" AS` | `WITH NO DATA` | `"schema"."name"` |
| Function | `CREATE FUNCTION "schema"."name"({args})` | (N/A) | `"schema"."name"({args})` |
| Trigger | `CREATE TRIGGER "name" {condition} ON "schema"."table"` | (N/A) | `name` (unquoted) |

## Troubleshooting

### Dollar-Quoting in Functions (`$$`)

**Problem**: Using `$$` for dollar-quoted strings in PostgreSQL functions causes template errors.

**Explanation**: Dbsamizdapper uses Python's `string.Template` to process SQL templates. In Python templates, `$$` is interpreted as an escaped `$` character, which conflicts with PostgreSQL's `$$` dollar-quoting syntax.

**Solution**: Use a tag instead of `$$`. Any tag works (e.g., `$BODY$`, `$FUNC$`, `$CODE$`):

> **See also**: [Template Variables Reference](#template-variables-reference) for information about how template variables are processed.

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

### Function Signature Handling Issues

#### Signature Duplication Error

**Problem**: Getting syntax errors like `CREATE FUNCTION name(sig)(sig)` when creating functions.

**Explanation**: This happens when you include `CREATE FUNCTION` in your `sql_template` AND use `${preamble}`. The `${preamble}` already includes `CREATE FUNCTION {schema}.{name}({signature})`, so adding it again causes duplication.

**Solution**: Choose one approach:
- **Option A**: Include full `CREATE FUNCTION` in template, set `function_arguments_signature = ""`
- **Option B** (Recommended): Use `${preamble}`, omit `CREATE FUNCTION` from template

```python
# ❌ This will cause duplication
class BadFunction(SamizdatFunction):
    function_arguments_signature = "name TEXT"
    sql_template = """
        CREATE FUNCTION "public"."BadFunction"(name TEXT)  # Don't include this!
        ${preamble}  # This already includes CREATE FUNCTION
        RETURNS TEXT AS
        $BODY$
        SELECT name;
        $BODY$
        LANGUAGE SQL;
    """

# ✅ Correct: Use ${preamble} only
class GoodFunction(SamizdatFunction):
    function_arguments_signature = "name TEXT"
    sql_template = """
        ${preamble}  # This includes CREATE FUNCTION automatically
        RETURNS TEXT AS
        $BODY$
        SELECT name;
        $BODY$
        LANGUAGE SQL;
    """
```

#### Empty Signature Still Adds Parentheses

**Problem**: Even when `function_arguments_signature = ""`, the generated SQL includes `()`.

**Explanation**: This is expected behavior. `creation_identity()` always includes parentheses: `"schema"."name"({args})`. When `function_arguments_signature = ""`, it becomes `"schema"."name"()`, which is correct SQL for a function with no parameters.

**Solution**: This is not an error - it's the correct behavior. If you want a function with no parameters, use `function_arguments_signature = ""` and the `()` will be automatically added.

```python
# ✅ This is correct - the () will be added automatically
class NoParamFunction(SamizdatFunction):
    function_arguments_signature = ""  # No parameters
    sql_template = """
        ${preamble}  # Generates: CREATE FUNCTION "public"."NoParamFunction"()
        RETURNS TEXT AS
        $BODY$
        SELECT 'Hello';
        $BODY$
        LANGUAGE SQL;
    """
```

#### Missing CREATE FUNCTION Error

**Problem**: Getting errors about missing `CREATE FUNCTION` statement.

**Explanation**: Your `sql_template` must either:
1. Include a complete `CREATE FUNCTION` statement (Option A), OR
2. Use `${preamble}` which provides it automatically (Option B)

**Solution**: Ensure your template includes one of these:

```python
# ✅ Option A: Full CREATE FUNCTION in template
class FunctionA(SamizdatFunction):
    function_arguments_signature = ""
    sql_template = f"""
        CREATE FUNCTION {FunctionA.db_object_identity()}()
        RETURNS TEXT AS
        $BODY$
        SELECT 'test';
        $BODY$
        LANGUAGE SQL;
    """

# ✅ Option B: Use ${preamble} (recommended)
class FunctionB(SamizdatFunction):
    function_arguments_signature = ""
    sql_template = """
        ${preamble}  # Provides CREATE FUNCTION automatically
        RETURNS TEXT AS
        $BODY$
        SELECT 'test';
        $BODY$
        LANGUAGE SQL;
    """

# ❌ This will fail - no CREATE FUNCTION
class BadFunction(SamizdatFunction):
    function_arguments_signature = ""
    sql_template = """
        RETURNS TEXT AS  # Missing CREATE FUNCTION!
        $BODY$
        SELECT 'test';
        $BODY$
        LANGUAGE SQL;
    """
```

### SQL Template Processing Errors

When SQL generation fails, dbsamizdapper now provides enhanced error messages to help debug template issues.

#### Understanding Error Messages

Enhanced error messages include:
- **Original template**: The SQL template before variable substitution
- **Template variable substitutions**: What values replaced `${preamble}`, `${postamble}`, `${samizdatname}`
- **Function signature**: The `function_arguments_signature` used (for functions)
- **Final SQL**: The SQL that was attempted (always shown)
- **Error hints**: Automatic detection of common error patterns

#### Common Error Patterns

**1. Signature Duplication**

**Error**: `syntax error at or near "("`

**Problem**: Function signature appears twice in the generated SQL, like:
```sql
CREATE FUNCTION "name"()(target_ts TIMESTAMP WITH TIME ZONE)
```

**Cause**: Both `function_arguments_signature` attribute and the template include a signature.

**Solution**: Remove the signature from either:
- The `function_arguments_signature` attribute (if template has it), OR
- The template (if `function_arguments_signature` is set)

**Example**:
```python
# ❌ Problem: signature in both places
class BadFunction(SamizdatFunction):
    function_arguments_signature = "target_ts TIMESTAMP WITH TIME ZONE"
    sql_template = """
        ${preamble}
        (target_ts TIMESTAMP WITH TIME ZONE)  # ← Remove this
        RETURNS TIMESTAMP AS $BODY$
        SELECT target_ts;
        $BODY$ LANGUAGE SQL;
    """

# ✅ Solution 1: Remove from template
class GoodFunction1(SamizdatFunction):
    function_arguments_signature = "target_ts TIMESTAMP WITH TIME ZONE"
    sql_template = """
        ${preamble}
        RETURNS TIMESTAMP AS $BODY$
        SELECT target_ts;
        $BODY$ LANGUAGE SQL;
    """

# ✅ Solution 2: Remove from attribute
class GoodFunction2(SamizdatFunction):
    function_arguments_signature = ""  # ← Empty, template has it
    sql_template = """
        ${preamble}
        (target_ts TIMESTAMP WITH TIME ZONE)
        RETURNS TIMESTAMP AS $BODY$
        SELECT target_ts;
        $BODY$ LANGUAGE SQL;
    """
```

**2. Missing CREATE FUNCTION**

**Error**: `syntax error at or near "RETURNS"`

**Problem**: Template includes `RETURNS` but no `CREATE FUNCTION` statement.

**Cause**: Template doesn't start with `${preamble}` or `${preamble}` wasn't substituted properly.

**Solution**: Ensure your template starts with `${preamble}`:

```python
# ❌ Missing CREATE FUNCTION
class BadFunction(SamizdatFunction):
    sql_template = """
        RETURNS TEXT AS $BODY$
        SELECT 'test';
        $BODY$ LANGUAGE SQL;
    """

# ✅ Correct: Use ${preamble}
class GoodFunction(SamizdatFunction):
    sql_template = """
        ${preamble}
        RETURNS TEXT AS $BODY$
        SELECT 'test';
        $BODY$ LANGUAGE SQL;
    """
```

**3. Invalid Template Variable**

**Error**: `syntax error at or near "$"`

**Problem**: Unsubstituted template variable found in SQL.

**Cause**: Template variable not recognized or typo in variable name.

**Solution**: Use only recognized variables:
- `${preamble}` - CREATE statement prefix
- `${postamble}` - WITH NO DATA suffix (for materialized views)
- `${samizdatname}` - Fully qualified object name

```python
# ❌ Invalid variable
class BadView(SamizdatView):
    sql_template = """
        ${preamble} SELECT $invalid FROM users ${postamble}
    """

# ✅ Use valid variables
class GoodView(SamizdatView):
    sql_template = """
        ${preamble} SELECT * FROM users ${postamble}
    """
```

#### Debugging Tips

**1. Enable Verbose Output**

Use `-v` flag to see the SQL being executed:

```bash
python -m dbsamizdat.runner sync postgresql:///mydb myapp.views -v
```

**2. Inspect Generated SQL**

When an error occurs, the error message shows:
- The original template
- What substitutions were made
- The final SQL that failed

**3. Test Templates in Isolation**

You can test template processing without executing:

```python
from dbsamizdat import SamizdatView

class TestView(SamizdatView):
    sql_template = "${preamble} SELECT 1 ${postamble}"

# See what SQL would be generated
print(TestView.create())
# Output: CREATE VIEW "public"."TestView" AS  SELECT 1
```

**4. Check Function Signatures**

For functions, verify `function_arguments_signature` matches what's in the database:

```python
# Check what signature PostgreSQL expects
# The error message will show candidate signatures if there's a mismatch
```

**5. Review Error Context**

Enhanced error messages automatically detect common patterns and provide hints. Look for the 💡 Hint section in error output.

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
