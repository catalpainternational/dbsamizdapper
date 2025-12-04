"""
Integration tests for libdb module.

Tests database state comparison, dbinfo parsing, and state equality checks.
"""

import pytest

from dbsamizdat.libdb import dbinfo_to_class, dbstate_equals_definedstate, get_dbstate
from dbsamizdat.runner import cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatView
from dbsamizdat.samtypes import FQTuple

# ==================== Test Samizdat Definitions ====================


class TestView(SamizdatView):
    """Test view for libdb testing"""

    sql_template = """
        ${preamble}
        SELECT 1 as value
        ${postamble}
    """


class AnotherTestView(SamizdatView):
    """Another test view"""

    sql_template = """
        ${preamble}
        SELECT 2 as value
        ${postamble}
    """


# ==================== get_dbstate Tests ====================


@pytest.mark.integration
def test_get_dbstate_returns_empty_for_empty_database(clean_db):
    """Test that get_dbstate returns empty set for empty database"""
    args = clean_db

    with get_cursor(args) as cursor:
        dbstate = list(get_dbstate(cursor))

    assert len(dbstate) == 0


@pytest.mark.integration
def test_get_dbstate_detects_created_views(clean_db):
    """Test that get_dbstate detects views created by dbsamizdat"""
    args = clean_db
    args.samizdatmodules = []

    # Create a view
    cmd_sync(args, [TestView])

    with get_cursor(args) as cursor:
        dbstate = list(get_dbstate(cursor))

    # Should find the view we created
    assert len(dbstate) > 0
    view_names = {FQTuple.fqify((state.schemaname, state.viewname)) for state in dbstate}
    assert TestView.fq() in view_names


@pytest.mark.integration
def test_get_dbstate_includes_comment_content(clean_db):
    """Test that get_dbstate includes comment content for dbsamizdat objects"""
    args = clean_db
    args.samizdatmodules = []

    # Create a view
    cmd_sync(args, [TestView])

    with get_cursor(args) as cursor:
        dbstate = list(get_dbstate(cursor))

    # Find our view
    test_view_fq = TestView.fq()
    test_view_state = next((s for s in dbstate if FQTuple.fqify((s.schemaname, s.viewname)) == test_view_fq), None)
    assert test_view_state is not None
    assert test_view_state.commentcontent is not None
    assert "dbsamizdat" in test_view_state.commentcontent.lower()


# ==================== dbstate_equals_definedstate Tests ====================


@pytest.mark.integration
def test_dbstate_equals_definedstate_when_synced(clean_db):
    """Test that dbstate_equals_definedstate returns True when synced"""
    args = clean_db
    args.samizdatmodules = []

    # Sync views
    cmd_sync(args, [TestView, AnotherTestView])

    with get_cursor(args) as cursor:
        result = dbstate_equals_definedstate(cursor, [TestView, AnotherTestView])

    assert result.issame is True
    assert len(result.excess_dbstate) == 0
    assert len(result.excess_definedstate) == 0


@pytest.mark.integration
def test_dbstate_equals_definedstate_detects_missing_views(clean_db):
    """Test that dbstate_equals_definedstate detects missing views"""
    args = clean_db
    args.samizdatmodules = []

    # Sync only one view
    cmd_sync(args, [TestView])

    with get_cursor(args) as cursor:
        # Check against both views
        result = dbstate_equals_definedstate(cursor, [TestView, AnotherTestView])

    assert result.issame is False
    # excess_definedstate contains class objects, not FQTuples
    excess_classes = set(result.excess_definedstate)
    assert AnotherTestView in excess_classes


@pytest.mark.integration
def test_dbstate_equals_definedstate_detects_extra_views(clean_db):
    """Test that dbstate_equals_definedstate detects extra views in DB"""
    args = clean_db
    args.samizdatmodules = []

    # Create both views
    cmd_sync(args, [TestView, AnotherTestView])

    with get_cursor(args) as cursor:
        # Check against only one view - should detect AnotherTestView as extra
        result = dbstate_equals_definedstate(cursor, [TestView])

    assert result.issame is False
    # AnotherTestView should be in excess_dbstate (in DB but not in defined list)
    # excess_dbstate contains reconstructed class objects (from dbinfo_to_class)
    excess_classes = set(result.excess_dbstate)
    excess_fqs = {cls.fq() for cls in excess_classes}
    assert AnotherTestView.fq() in excess_fqs


@pytest.mark.integration
def test_dbstate_equals_definedstate_ignores_non_dbsamizdat_views(clean_db):
    """Test that dbstate_equals_definedstate ignores views not managed by dbsamizdat"""
    args = clean_db

    # Create a view manually (not through dbsamizdat)
    with get_cursor(args) as cursor:
        cursor.execute("DROP VIEW IF EXISTS manual_view CASCADE;")
        cursor.execute("""
            CREATE VIEW manual_view AS SELECT 1;
        """)

        # Verify get_dbstate doesn't return it (no dbsamizdat comment)
        dbstate = list(get_dbstate(cursor))
        manual_view_states = [s for s in dbstate if s.schemaname == "public" and s.viewname == "manual_view"]
        assert len(manual_view_states) == 0  # Should be filtered out

        # Check state - should not include manual_view
        result = dbstate_equals_definedstate(cursor, [])

    # excess_dbstate should be empty since manual_view has no comment
    assert len(result.excess_dbstate) == 0


# ==================== dbinfo_to_class Tests ====================


@pytest.mark.integration
def test_dbinfo_to_class_reconstructs_view(clean_db):
    """Test that dbinfo_to_class can reconstruct a view class from DB info"""
    args = clean_db
    args.samizdatmodules = []

    # Create a view
    cmd_sync(args, [TestView])

    with get_cursor(args) as cursor:
        dbstate = list(get_dbstate(cursor))
        test_view_fq = TestView.fq()
        test_view_state = next((s for s in dbstate if FQTuple.fqify((s.schemaname, s.viewname)) == test_view_fq), None)
        assert test_view_state is not None

        # Try to reconstruct the class
        reconstructed = dbinfo_to_class(test_view_state)

    # Should be able to reconstruct basic info
    assert reconstructed is not None
    # The reconstructed class should have the same FQ
    assert reconstructed.fq() == TestView.fq()


@pytest.mark.integration
def test_dbinfo_to_class_handles_materialized_views(clean_db):
    """Test that dbinfo_to_class works with materialized views"""
    from dbsamizdat.samizdat import SamizdatMaterializedView

    class TestMatView(SamizdatMaterializedView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    args = clean_db
    args.samizdatmodules = []

    # Create materialized view
    cmd_sync(args, [TestMatView])

    with get_cursor(args) as cursor:
        dbstate = list(get_dbstate(cursor))
        matview_fq = TestMatView.fq()
        matview_state = next((s for s in dbstate if FQTuple.fqify((s.schemaname, s.viewname)) == matview_fq), None)
        assert matview_state is not None

        # Reconstruct
        reconstructed = dbinfo_to_class(matview_state)

    assert reconstructed is not None
    assert reconstructed.fq() == TestMatView.fq()
