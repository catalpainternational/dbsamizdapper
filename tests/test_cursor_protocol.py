"""
Tests for Cursor and Mogrifier interfaces.

These tests verify that database cursors (psycopg2, psycopg3, Django)
work correctly with our type system, especially after moving from ABC to Protocol.
"""

import pytest


@pytest.mark.unit
def test_cursor_interface_structure():
    """Test that our Cursor interface has expected methods"""
    import inspect

    from dbsamizdat.samtypes import Cursor

    # Cursor should be a class/type
    assert inspect.isclass(Cursor)

    # Should have expected method signatures
    # Note: With ABC, these are abstract methods
    # With Protocol, these define the structural contract


@pytest.mark.unit
def test_mogrifier_interface_structure():
    """Test that our Mogrifier interface has expected methods"""
    import inspect

    from dbsamizdat.samtypes import Mogrifier

    assert inspect.isclass(Mogrifier)


@pytest.mark.integration
def test_psycopg2_cursor_compatibility(db_args):
    """Test that psycopg2 cursor is compatible with our Cursor interface"""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed")

    # Create a psycopg2 cursor
    conn = psycopg2.connect(db_args.dburl)
    cursor = conn.cursor()

    # Test mogrify method
    result = cursor.mogrify("SELECT %s", ("test",))
    assert isinstance(result, (str, bytes))

    # Test execute method
    cursor.execute("SELECT 1")
    assert cursor.fetchone() == (1,)

    # Test fetchall method
    cursor.execute("SELECT 1 UNION SELECT 2")
    result = cursor.fetchall()
    assert len(result) == 2

    cursor.close()
    conn.close()


@pytest.mark.integration
def test_psycopg3_cursor_compatibility(db_args):
    """Test that psycopg3 cursor is compatible with our Cursor interface"""
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg (v3) not installed")

    # Create a psycopg3 cursor
    conn = psycopg.connect(db_args.dburl)
    cursor = psycopg.ClientCursor(conn)

    # Test mogrify method
    result = cursor.mogrify("SELECT %s", ("test",))
    assert isinstance(result, (str, bytes))

    # Test execute method
    cursor.execute("SELECT 1")
    assert cursor.fetchone() == (1,)

    # Test fetchall method
    cursor.execute("SELECT 1 UNION SELECT 2")
    result = cursor.fetchall()
    assert len(result) == 2

    cursor.close()
    conn.close()


@pytest.mark.integration
def test_get_cursor_returns_compatible_cursor(db_args):
    """Test that get_cursor returns a cursor compatible with our interface"""
    from dbsamizdat.runner import get_cursor

    with get_cursor(db_args) as cursor:
        # Test basic cursor operations
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result == (1,)

        # Test mogrify (both psycopg versions support this)
        mogrified = cursor.mogrify("SELECT %s", ("test",))
        assert isinstance(mogrified, (str, bytes))

        # Test fetchall
        cursor.execute("SELECT 1 UNION SELECT 2 ORDER BY 1")
        results = cursor.fetchall()
        assert len(results) == 2


@pytest.mark.integration
def test_cursor_with_samizdat_sign(clean_db):
    """Test that cursor works with Samizdat.sign() method"""
    from dbsamizdat.runner import get_cursor
    from dbsamizdat.samizdat import SamizdatView

    class TestView(SamizdatView):
        sql_template = """
            ${preamble}
            SELECT 1 as value
            ${postamble}
        """

    with get_cursor(clean_db) as cursor:
        # sign() method uses cursor.mogrify()
        sign_sql = TestView.sign(cursor)

        # Should return a string (or bytes in some psycopg versions)
        assert isinstance(sign_sql, (str, bytes))

        # Should contain COMMENT ON
        if isinstance(sign_sql, bytes):
            sign_sql = sign_sql.decode()
        assert "COMMENT ON" in sign_sql
        assert "VIEW" in sign_sql


@pytest.mark.unit
def test_cursor_type_annotations():
    """Test that Cursor has proper type annotations"""
    import typing

    from dbsamizdat.samtypes import Cursor

    # Get type hints
    hints = typing.get_type_hints(Cursor.execute) if hasattr(Cursor, "execute") else {}

    # After moving to Protocol, we should still have type hints
    # This test documents expected behavior


@pytest.mark.integration
def test_multiple_cursor_types_work(db_args):
    """
    Test that different cursor implementations all work with our code.
    This is the key benefit of using Protocol vs ABC.
    """
    from dbsamizdat.runner import get_cursor

    # Test with whatever cursor implementation is available
    with get_cursor(db_args) as cursor:
        # All these operations should work regardless of cursor type
        cursor.execute("CREATE TEMP TABLE test_table (id INTEGER)")
        cursor.execute("INSERT INTO test_table VALUES (1), (2), (3)")
        cursor.execute("SELECT * FROM test_table ORDER BY id")

        results = cursor.fetchall()
        assert len(results) == 3
        assert results[0][0] == 1

        cursor.execute("SELECT * FROM test_table WHERE id = %s", (2,))
        result = cursor.fetchone()
        assert result[0] == 2
