"""
Simple example demonstrating dbsamizdapper usage without Django.

This example shows:
1. Defining samizdat classes in a module
2. Using the CLI to sync to database
3. Using the library API programmatically
"""

from dbsamizdat import SamizdatView, SamizdatMaterializedView, SamizdatTable

# Example 1: Simple view
class CurrentTime(SamizdatView):
    """A simple view showing current time"""
    sql_template = """
        ${preamble}
        SELECT NOW() as current_time
        ${postamble}
    """


# Example 2: Table definition
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


# Example 3: Materialized view with dependencies
class CachedTime(SamizdatMaterializedView):
    """Materialized view depending on CurrentTime"""
    deps_on = {CurrentTime}
    sql_template = """
        ${preamble}
        SELECT * FROM "CurrentTime"
        ${postamble}
    """


# Example 4: View with unmanaged dependency
class OrdersSummary(SamizdatView):
    """View that depends on an unmanaged table"""
    # Reference to a table not managed by dbsamizdat
    deps_on_unmanaged = {"orders"}
    sql_template = """
        ${preamble}
        SELECT 
            DATE(created_at) as order_date,
            COUNT(*) as order_count,
            SUM(total) as total_revenue
        FROM orders
        GROUP BY DATE(created_at)
        ${postamble}
    """


# Example 5: Function with dollar-quoting (note: use $BODY$ not $$)
from dbsamizdat import SamizdatFunction

class ExampleFunction(SamizdatFunction):
    """Example function showing correct dollar-quoting syntax"""
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN 'Hello from function!';
        END;
        $BODY$
        LANGUAGE plpgsql;
    """
    # Note: PostgreSQL's $$ syntax does NOT work here because it clashes
    # with Python's string.Template. Always use a tag like $BODY$ instead.


if __name__ == "__main__":
    # Example: Using library API
    from dbsamizdat import sync
    
    # Sync using module name (this file would be imported)
    # In practice, you'd use: sync("postgresql:///mydb", samizdatmodules=["examples.simple_example"])
    print("To sync these samizdats, run:")
    print("  python -m dbsamizdat.runner sync postgresql:///mydb examples.simple_example")
    print("\nOr use the library API:")
    print("  from dbsamizdat import sync")
    print("  sync('postgresql:///mydb', samizdatmodules=['examples.simple_example'])")
    print("\nNote: When writing PostgreSQL functions, use $BODY$ instead of $$")
    print("      because $$ clashes with Python's template processing.")

