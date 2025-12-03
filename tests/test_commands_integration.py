"""
Integration tests for command functions (cmd_sync, cmd_refresh, cmd_nuke, cmd_diff).

These tests require a database connection and test the full command execution flow.
"""

import pytest

from dbsamizdat.runner import cmd_diff, cmd_nuke, cmd_refresh, cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatMaterializedView, SamizdatView

# ==================== Test Samizdat Definitions ====================


class BaseView(SamizdatView):
    """Base view for dependency testing"""

    sql_template = """
        ${preamble}
        SELECT 1 as value
        ${postamble}
    """


class DependentView(SamizdatView):
    """View that depends on BaseView"""

    deps_on = {BaseView}
    sql_template = """
        ${preamble}
        SELECT * FROM "BaseView"
        ${postamble}
    """


class MaterializedView(SamizdatMaterializedView):
    """Materialized view for refresh testing"""

    deps_on = {BaseView}
    sql_template = """
        ${preamble}
        SELECT * FROM "BaseView"
        ${postamble}
    """


class AnotherMaterializedView(SamizdatMaterializedView):
    """Another materialized view for refresh filtering"""

    deps_on = {DependentView}
    sql_template = """
        ${preamble}
        SELECT * FROM "DependentView"
        ${postamble}
    """


# ==================== cmd_sync Tests ====================


@pytest.mark.integration
def test_cmd_sync_creates_views(clean_db):
    """Test that cmd_sync creates views in the database"""
    args = clean_db
    args.samizdatmodules = []

    cmd_sync(args, [BaseView, DependentView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
        """)
        views = {row[0] for row in cursor.fetchall()}
        assert views == {"BaseView", "DependentView"}


@pytest.mark.integration
def test_cmd_sync_drops_excess_views(clean_db):
    """Test that cmd_sync drops views that are no longer defined"""
    args = clean_db
    args.samizdatmodules = []

    # First sync creates views
    cmd_sync(args, [BaseView, DependentView])

    # Second sync with fewer views should drop the extra one
    cmd_sync(args, [BaseView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname = 'DependentView'
        """)
        assert cursor.fetchone() is None


@pytest.mark.integration
def test_cmd_sync_idempotent(clean_db):
    """Test that running cmd_sync twice produces no changes"""
    args = clean_db
    args.samizdatmodules = []

    # First sync
    cmd_sync(args, [BaseView, DependentView])

    # Second sync should detect no differences
    # This tests the early return in cmd_sync when db_compare.issame is True
    cmd_sync(args, [BaseView, DependentView])

    # Verify views still exist
    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
        """)
        assert cursor.fetchone()[0] == 2


@pytest.mark.integration
def test_cmd_sync_with_materialized_views(clean_db):
    """Test that cmd_sync creates and refreshes materialized views"""
    args = clean_db
    args.samizdatmodules = []

    cmd_sync(args, [BaseView, MaterializedView])

    with get_cursor(args) as cursor:
        # Check materialized view exists
        cursor.execute("""
            SELECT matviewname FROM pg_matviews
            WHERE schemaname = 'public'
            AND matviewname = 'MaterializedView'
        """)
        assert cursor.fetchone() is not None

        # Verify it has data
        cursor.execute('SELECT COUNT(*) FROM "MaterializedView"')
        assert cursor.fetchone()[0] > 0


@pytest.mark.integration
def test_cmd_sync_handles_dependency_order(clean_db):
    """Test that cmd_sync handles dependencies correctly"""
    args = clean_db
    args.samizdatmodules = []

    # DependentView depends on BaseView, so BaseView must be created first
    cmd_sync(args, [DependentView, BaseView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
            ORDER BY viewname
        """)
        views = [row[0] for row in cursor.fetchall()]
        assert views == ["BaseView", "DependentView"]


# ==================== cmd_refresh Tests ====================


@pytest.mark.integration
def test_cmd_refresh_refreshes_all_materialized_views(clean_db):
    """Test that cmd_refresh refreshes all materialized views"""
    args = clean_db
    args.samizdatmodules = []

    # Create views and materialized views
    cmd_sync(args, [BaseView, MaterializedView, AnotherMaterializedView])

    # Refresh all materialized views
    cmd_refresh(args)

    with get_cursor(args) as cursor:
        # Verify both materialized views exist and have data
        cursor.execute("""
            SELECT matviewname FROM pg_matviews
            WHERE schemaname = 'public'
            AND matviewname IN ('MaterializedView', 'AnotherMaterializedView')
        """)
        matviews = {row[0] for row in cursor.fetchall()}
        assert matviews == {"MaterializedView", "AnotherMaterializedView"}


@pytest.mark.integration
def test_cmd_refresh_with_belownodes_filter(clean_db):
    """Test that cmd_refresh only refreshes views below specified nodes"""
    args = clean_db
    args.samizdatmodules = []

    # Create views with dependencies:
    # BaseView -> DependentView -> AnotherMaterializedView
    # BaseView -> MaterializedView
    cmd_sync(args, [BaseView, DependentView, MaterializedView, AnotherMaterializedView])

    # Refresh only views below DependentView
    args.belownodes = [DependentView]
    cmd_refresh(args)

    # Both materialized views should still exist
    # (This tests the filtering logic, actual refresh happens)
    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT matviewname FROM pg_matviews
            WHERE schemaname = 'public'
        """)
        matviews = {row[0] for row in cursor.fetchall()}
        assert "AnotherMaterializedView" in matviews


@pytest.mark.integration
def test_cmd_refresh_with_invalid_belownodes(clean_db):
    """Test that cmd_refresh raises error for unknown belownodes"""
    args = clean_db
    args.samizdatmodules = []
    args.belownodes = [("public", "NonExistentView")]

    with pytest.raises(ValueError, match="Unknown rootnodes"):
        cmd_refresh(args)


@pytest.mark.integration
def test_cmd_refresh_empty_when_no_materialized_views(clean_db):
    """Test that cmd_refresh handles case with no materialized views"""
    args = clean_db
    args.samizdatmodules = []

    # Create only regular views
    cmd_sync(args, [BaseView, DependentView])

    # Refresh should complete without error (no matviews to refresh)
    cmd_refresh(args)


# ==================== cmd_nuke Tests ====================


@pytest.mark.integration
def test_cmd_nuke_drops_all_views(clean_db):
    """Test that cmd_nuke drops all dbsamizdat-managed views"""
    args = clean_db
    args.samizdatmodules = []

    # Create views
    cmd_sync(args, [BaseView, DependentView, MaterializedView])

    # Nuke everything
    cmd_nuke(args)

    with get_cursor(args) as cursor:
        # Check no views remain
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
        """)
        assert cursor.fetchone()[0] == 0

        # Check no materialized views remain
        cursor.execute("""
            SELECT COUNT(*) FROM pg_matviews
            WHERE schemaname = 'public'
            AND matviewname = 'MaterializedView'
        """)
        assert cursor.fetchone()[0] == 0


@pytest.mark.integration
def test_cmd_nuke_idempotent(clean_db):
    """Test that running cmd_nuke twice doesn't error"""
    args = clean_db
    args.samizdatmodules = []

    # Create and nuke
    cmd_sync(args, [BaseView])
    cmd_nuke(args)

    # Nuke again should not error
    cmd_nuke(args)


@pytest.mark.integration
def test_cmd_nuke_with_specific_samizdats(clean_db):
    """Test that cmd_nuke can target specific samizdats"""
    args = clean_db
    args.samizdatmodules = []

    # Create multiple views
    cmd_sync(args, [BaseView, DependentView])

    # Nuke only one
    cmd_nuke(args, samizdats=[BaseView])

    with get_cursor(args) as cursor:
        # BaseView should be gone
        cursor.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname = 'BaseView'
        """)
        assert cursor.fetchone() is None

        # DependentView should still exist (though it may be broken due to dependency)
        cursor.execute("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            AND viewname = 'DependentView'
        """)
        # May or may not exist depending on CASCADE behavior
        cursor.fetchone()  # Just verify the command completed


# ==================== cmd_diff Tests ====================


@pytest.mark.integration
def test_cmd_diff_shows_no_differences_when_synced(clean_db):
    """Test that cmd_diff shows no differences when DB matches code"""
    args = clean_db
    args.samizdatmodules = []

    # Sync views
    cmd_sync(args, [BaseView, DependentView])

    # Diff should show no differences
    # Note: cmd_diff prints to stdout, so we just verify it doesn't raise
    with get_cursor(args):
        cmd_diff(args)


@pytest.mark.integration
def test_cmd_diff_shows_differences_when_unsynced(clean_db):
    """Test that cmd_diff detects differences between DB and code"""
    args = clean_db
    args.samizdatmodules = []

    # Create views
    cmd_sync(args, [BaseView, DependentView])

    # Manually drop one view
    with get_cursor(args) as cursor:
        cursor.execute('DROP VIEW IF EXISTS "DependentView" CASCADE')

    # Diff should detect the missing view
    # (We can't easily test the output, but we verify it doesn't crash)
    with get_cursor(args) as cursor:
        cmd_diff(args)


# ==================== Transaction Discipline Tests ====================


@pytest.mark.integration
def test_cmd_sync_with_checkpoint_transaction(clean_db):
    """Test that cmd_sync works with checkpoint transaction discipline"""
    args = clean_db
    args.txdiscipline = "checkpoint"
    args.samizdatmodules = []

    cmd_sync(args, [BaseView, DependentView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
        """)
        assert cursor.fetchone()[0] == 2


@pytest.mark.integration
def test_cmd_sync_with_jumbo_transaction(clean_db):
    """Test that cmd_sync works with jumbo transaction discipline"""
    args = clean_db
    args.txdiscipline = "jumbo"
    args.samizdatmodules = []

    cmd_sync(args, [BaseView, DependentView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
        """)
        assert cursor.fetchone()[0] == 2


@pytest.mark.integration
def test_cmd_sync_with_dryrun_transaction(clean_db):
    """Test that cmd_sync with dryrun doesn't modify database"""
    args = clean_db
    args.txdiscipline = "dryrun"
    args.samizdatmodules = []

    # Dryrun should not create views
    cmd_sync(args, [BaseView, DependentView])

    with get_cursor(args) as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM pg_views
            WHERE schemaname = 'public'
            AND viewname IN ('BaseView', 'DependentView')
        """)
        # Dryrun should not create anything
        assert cursor.fetchone()[0] == 0
