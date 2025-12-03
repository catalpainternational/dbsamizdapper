"""
Integration tests for the executor module.

Tests transaction handling, error recovery, and execution flow.
"""

import pytest

from dbsamizdat.exceptions import DatabaseError
from dbsamizdat.runner import cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatView

# ==================== Test Samizdat Definitions ====================


class SimpleView(SamizdatView):
    """Simple view for executor testing"""

    sql_template = """
        ${preamble}
        SELECT 1 as value
        ${postamble}
    """


class ViewWithError(SamizdatView):
    """View that will cause an error when created"""

    sql_template = """
        ${preamble}
        SELECT * FROM nonexistent_table
        ${postamble}
    """


# ==================== Executor Transaction Tests ====================


@pytest.mark.integration
def test_executor_rollback_on_error(clean_db):
    """Test that executor rolls back transaction on error"""
    args = clean_db
    args.txdiscipline = "checkpoint"
    args.samizdatmodules = []

    # Try to sync a view with invalid SQL
    # This should trigger an error in the executor
    with pytest.raises(DatabaseError):
        cmd_sync(args, [ViewWithError])

    # Verify nothing was created
    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname = 'ViewWithError'
        """)
        assert cursor.fetchone()[0] == 0


@pytest.mark.integration
def test_executor_handles_multiple_operations(clean_db):
    """Test that executor handles multiple operations in sequence"""
    args = clean_db
    args.samizdatmodules = []

    # Create multiple views - executor should handle all of them
    cmd_sync(args, [SimpleView])

    # Add another view
    class AnotherView(SamizdatView):
        sql_template = """
            ${preamble}
            SELECT 2 as value
            ${postamble}
        """

    cmd_sync(args, [SimpleView, AnotherView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
        """)
        assert cursor.fetchone()[0] == 2


@pytest.mark.integration
def test_executor_savepoint_handling(clean_db):
    """Test that executor uses savepoints correctly with checkpoint mode"""
    args = clean_db
    args.txdiscipline = "checkpoint"
    args.samizdatmodules = []

    # Create a valid view first
    cmd_sync(args, [SimpleView])

    # Verify it exists
    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname = 'SimpleView'
        """)
        assert cursor.fetchone() is not None


@pytest.mark.integration
def test_executor_jumbo_transaction_all_or_nothing(clean_db):
    """Test that jumbo transaction is all-or-nothing"""
    args = clean_db
    args.txdiscipline = "jumbo"
    args.samizdatmodules = []

    # Create multiple views in one transaction
    class View1(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class View2(SamizdatView):
        sql_template = "${preamble} SELECT 2 ${postamble}"

    cmd_sync(args, [View1, View2])

    # Both should exist
    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('View1', 'View2')
        """)
        assert cursor.fetchone()[0] == 2
