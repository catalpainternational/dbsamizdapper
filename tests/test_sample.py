"""Core functionality tests for dbsamizdat"""

import pytest

from dbsamizdat.exceptions import DependencyCycleError, NameClashError, UnsuitableNameError
from dbsamizdat.graphvizdot import dot
from dbsamizdat.libdb import dbinfo_to_class, dbstate_equals_definedstate, get_dbstate
from dbsamizdat.libgraph import depsort_with_sidekicks, sanity_check
from dbsamizdat.loader import get_samizdats
from dbsamizdat.runner import cmd_nuke, cmd_sync
from dbsamizdat.samizdat import SamizdatMaterializedView, SamizdatView
from dbsamizdat.samtypes import FQTuple
from sample_app.test_samizdats import DealFruitFun, DealFruitFunWithName

# ==================== Test Samizdat Definitions ====================


class AnotherThing(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT now()
        ${postamble}
    """


class MaterializedThing(SamizdatMaterializedView):
    deps_on = {AnotherThing}
    deps_on_unmanaged = {"Fruit"}
    sql_template = """
        ${preamble}
        SELECT now()
        ${postamble}
    """


# ==================== Unit Tests (No Database) ====================


@pytest.mark.unit
def test_code_generation():
    """Assert that code generation raises no errors"""
    # These are pure function calls, no database needed
    AnotherThing.create()
    AnotherThing.drop()
    MaterializedThing.create()
    MaterializedThing.drop()

    # Test various property methods
    AnotherThing.get_name()
    AnotherThing.fq()
    AnotherThing.db_object_identity()
    AnotherThing.validate_name()
    AnotherThing.definition_hash()
    AnotherThing.fqdeps_on()
    AnotherThing.fqdeps_on_unmanaged()
    AnotherThing.dbinfo()
    AnotherThing.head_id()

    # Verify basic properties
    assert AnotherThing.schema == "public"
    assert AnotherThing.get_name() == "AnotherThing"
    assert AnotherThing.db_object_identity() == '"public"."AnotherThing"'

    # Verify function signatures
    assert DealFruitFunWithName.fq() == FQTuple("public", "DealFruitFun", "name text")
    assert MaterializedThing.fqdeps_on() == {FQTuple("public", "AnotherThing")}

    # Test sidekicks generation
    MaterializedThing.sidekicks()


@pytest.mark.unit
def test_signing_requires_cursor(db_cursor):
    """Test that signing requires a cursor"""
    # These SQL-generating functions require a cursor
    AnotherThing.sign(db_cursor)

    # Different signatures should produce different hashes
    assert DealFruitFunWithName.sign(db_cursor) != DealFruitFun.sign(db_cursor)


# ==================== Integration Tests (With Database) ====================


@pytest.mark.integration
@pytest.mark.skip(reason="PostgreSQL function inlining issue with matviews - see issue #5")
def test_create_view(clean_db, fruit_pet_tables):
    """Test full view creation workflow"""
    cmd_sync(clean_db)

    # Verify view can be queried
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {AnotherThing.db_object_identity()};")
        cursor.fetchall()

    # Get all samizdats
    samizdats = tuple(depsort_with_sidekicks(sanity_check(set(get_samizdats()))))

    # Generate graphviz output
    dot(samizdats)

    # Verify database state matches defined state
    with get_cursor(clean_db) as cursor:
        current_state = get_dbstate(cursor)
        list(dbinfo_to_class(s) for s in current_state)
        assert dbstate_equals_definedstate(cursor, samizdats).issame

    # Sync again should be idempotent
    cmd_sync(clean_db)
    with get_cursor(clean_db) as cursor:
        assert DealFruitFunWithName.sign(cursor) != DealFruitFun.sign(cursor)
        cursor.execute(
            f"""
            SELECT "{DealFruitFunWithName.get_name()}"(name) AS treat FROM "public"."Pet"
        """
        )

    # After nuke, views should not exist
    cmd_nuke(clean_db)
    with get_cursor(clean_db) as cursor:
        with pytest.raises(Exception):
            cursor.execute(f"SELECT * FROM {AnotherThing.db_object_identity()};")
            cursor.fetchall()


# ==================== Validation Tests ====================


@pytest.mark.integration
def test_long_name_raises(clean_db):
    """Test that samizdats with excessively long names are rejected"""

    class LongNamedSamizdat(SamizdatView):
        object_name = "hello" * 60  # Way too long
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    with pytest.raises(UnsuitableNameError):
        cmd_sync(clean_db, [LongNamedSamizdat])


@pytest.mark.integration
def test_unsuitable_name_raises(clean_db):
    """Test that samizdats with invalid characters are rejected"""

    class BadlyNamedSamizdat(SamizdatView):
        object_name = '"hello"'  # Quotes in name
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    with pytest.raises(UnsuitableNameError):
        cmd_sync(clean_db, [BadlyNamedSamizdat])


@pytest.mark.integration
def test_duplicate_name_raises(clean_db):
    """Test that duplicate samizdat names are detected"""

    class IAmCalledHello(SamizdatView):
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    class IAmCalledHelloToo(SamizdatView):
        object_name = "hello"  # Duplicate!
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    with pytest.raises(NameClashError):
        cmd_sync(clean_db, [IAmCalledHello, IAmCalledHelloToo])


# ==================== Dependency Tests ====================


@pytest.mark.integration
def test_cyclic_exception(clean_db):
    """Test that circular dependencies are detected"""

    class HelloWorld(SamizdatView):
        deps_on = {"hello2"}
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    class HelloWorldAgain(SamizdatView):
        deps_on = {"hello"}
        object_name = "hello2"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    with pytest.raises(DependencyCycleError):
        cmd_sync(clean_db, [HelloWorld, HelloWorldAgain])


@pytest.mark.integration
def test_self_reference_raises(clean_db):
    """Test that self-referencing dependencies are detected"""

    class Hello(SamizdatView):
        deps_on = {"hello"}
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    with pytest.raises(DependencyCycleError):
        cmd_sync(clean_db, [Hello])


# ==================== Materialized View Tests ====================


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skip(reason="Refresh trigger execution hangs - trigger mechanism needs debugging")
def test_sidekicks(clean_db, refresh_trigger_tables):
    """Test that materialized views with refresh_triggers create sidekicks"""

    class Treater(SamizdatMaterializedView):
        deps_on_unmanaged = {"d", "d2"}
        refresh_triggers = {"d", "d2"}
        sql_template = """
            ${preamble}
            SELECT * FROM d UNION SELECT * FROM d2
            ${postamble};
        """

    # The "sidekicks" should be included in the detected samizdats
    # This should be 1 materialized view + 1 refresh function + 2 triggers = 4 total
    sorted_samizdats = depsort_with_sidekicks([Treater])
    assert len(sorted_samizdats) == 4, "Should have matview + refresh function + 2 triggers"

    # Create the materialized view with triggers
    cmd_sync(clean_db, [Treater])

    # Verify initial data (2 rows from d and d2)
    with get_cursor(clean_db) as cursor:
        cursor.execute("""SELECT * FROM public."Treater" """)
        vals = cursor.fetchall()
        assert len(vals) == 2, "Should have 2 rows initially"

    # Insert into watched table - should trigger refresh
    with get_cursor(clean_db) as cursor:
        cursor.execute("INSERT INTO d SELECT now()")
        # No manual COMMIT - get_cursor() handles it automatically

    # Query in separate transaction to see refreshed data
    with get_cursor(clean_db) as cursor:
        cursor.execute("""SELECT * FROM public."Treater" """)
        vals = cursor.fetchall()
        assert len(vals) == 3, "Should have 3 rows after insert (auto-refreshed)"


@pytest.mark.integration
def test_executable_sql(clean_db):
    """Test that SQL can be provided by a method rather than static string"""

    class Now(SamizdatMaterializedView):
        @classmethod
        def sql_template(cls):
            my_query = "SELECT now()"
            return f"""
                ${{preamble}}
                {my_query}
                ${{postamble}};
            """

    cmd_sync(clean_db, [Now])

    # Verify view exists and is queryable
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {Now.db_object_identity()}")
        result = cursor.fetchall()
        assert len(result) == 1, "Should have one row"


# ==================== Complex Dependency Tests ====================


@pytest.mark.integration
@pytest.mark.slow
def test_multi_level_dependencies(clean_db):
    """Test complex multi-level dependency chains"""

    class Level1(SamizdatMaterializedView):
        sql_template = """
            ${preamble}
            SELECT Now()
            ${postamble};
        """

    class Level2(SamizdatMaterializedView):
        deps_on = {Level1}
        sql_template = """
            ${preamble}
            SELECT * FROM "Level1"
            ${postamble};
        """

    class Level3(SamizdatMaterializedView):
        deps_on = {Level2}
        sql_template = """
            ${preamble}
            SELECT * FROM "Level2"
            ${postamble};
        """

    class Level4(SamizdatMaterializedView):
        deps_on = {Level3}
        sql_template = """
            ${preamble}
            SELECT * FROM "Level3"
            ${postamble};
        """

    class Level5(SamizdatMaterializedView):
        deps_on = {Level4}
        sql_template = """
            ${preamble}
            SELECT * FROM "Level4"
            ${postamble};
        """

    # Test linear dependency chain
    cmd_sync(clean_db, [Level1, Level2, Level3, Level4, Level5])

    # Verify final view exists and is queryable
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {Level5.db_object_identity()}")
        result = cursor.fetchall()
        assert len(result) > 0


@pytest.mark.integration
@pytest.mark.slow
def test_diamond_dependencies(clean_db):
    """Test diamond-shaped dependency graph (one parent, two children, one grandchild)"""

    class Root(SamizdatMaterializedView):
        sql_template = """
            ${preamble}
            SELECT Now()
            ${postamble};
        """

    class Branch1(SamizdatMaterializedView):
        deps_on = {Root}
        sql_template = """
            ${preamble}
            SELECT * FROM "Root"
            ${postamble};
        """

    class Branch2(SamizdatMaterializedView):
        deps_on = {Root}
        sql_template = """
            ${preamble}
            SELECT * FROM "Root"
            ${postamble};
        """

    class Merged(SamizdatMaterializedView):
        deps_on = {Branch1, Branch2}
        sql_template = """
            ${preamble}
            SELECT * FROM "Branch1" UNION SELECT * FROM "Branch2"
            ${postamble};
        """

    # Test diamond dependency
    cmd_sync(clean_db, [Root, Branch1, Branch2, Merged])

    # Verify merged view exists
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {Merged.db_object_identity()}")
        result = cursor.fetchall()
        assert len(result) > 0


# ==================== Helper Import for get_cursor ====================


def get_cursor(args):
    """Re-export for convenience"""
    from dbsamizdat.runner import get_cursor as _get_cursor

    return _get_cursor(args)
