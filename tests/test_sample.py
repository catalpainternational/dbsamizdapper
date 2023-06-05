# content of test_sample.py
import os

import pytest
from dotenv import load_dotenv

from dbsamizdat.exceptions import DependencyCycleError, NameClashError, UnsuitableNameError
from dbsamizdat.graphvizdot import dot
from dbsamizdat.libdb import dbinfo_to_class, dbstate_equals_definedstate, get_dbstate
from dbsamizdat.libgraph import depsort_with_sidekicks, sanity_check
from dbsamizdat.loader import get_samizdats
from dbsamizdat.runner import ArgType, cmd_nuke, cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatMaterializedView, SamizdatView
from dbsamizdat.samtypes import FQTuple
from sample_app.test_samizdats import DealFruitFun, DealFruitFunWithName

load_dotenv()

DEFAULT_URL = os.environ.get("DBURL")


fruittable_SQL = """
    CREATE TABLE IF NOT EXISTS "Fruit" (
        id integer PRIMARY KEY,
        name varchar(100)
    );
    TRUNCATE "Fruit";

    INSERT INTO "Fruit"
    SELECT
        *
    FROM (
        VALUES
            (1, 'banana'),
            (2, 'pear'),
            (3, 'apple'),
            (4, 'rambutan')
    ) AS thefruits;

    CREATE TABLE IF NOT EXISTS "Pet" (
        id integer PRIMARY KEY,
        name varchar(100)
    );

    TRUNCATE "Pet";

    INSERT INTO "Pet"
    SELECT
        *
    FROM (
        VALUES
            (1, 'ocelot'),
            (2, 'khoi carp'),
            (3, 'rolypoly'),
            (4, 'drosophila')
    ) AS thepets;
"""


class AnotherThing(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT now()
        ${postamble}
    """


class MaterializedThing(SamizdatMaterializedView):
    deps_on = {AnotherThing}
    # refresh_triggers = {AnotherThing}
    deps_on_unmanaged = {"Fruit"}
    sql_template = """
        ${preamble}
        SELECT now()
        ${postamble}
    """


def test_code_generation():
    """
    Assert that code generation raises no errors
    """
    args = ArgType(txdiscipline="jumbo", verbosity=3)
    AnotherThing.create()
    AnotherThing.drop()
    MaterializedThing.create()
    MaterializedThing.drop()

    # Here are some useful outputs from the "SamizdatView"
    AnotherThing.get_name()
    AnotherThing.fq()
    AnotherThing.db_object_identity()
    AnotherThing.validate_name()
    AnotherThing.definition_hash()
    AnotherThing.fq()
    AnotherThing.fqdeps_on()
    AnotherThing.fqdeps_on_unmanaged()
    AnotherThing.dbinfo()
    # These SQL-generating functions require a cursor
    with get_cursor(args) as cursor:
        AnotherThing.sign(cursor)

    AnotherThing.create()
    AnotherThing.drop()

    AnotherThing.head_id()

    assert AnotherThing.schema == "public"
    assert AnotherThing.get_name() == "AnotherThing"
    assert AnotherThing.db_object_identity() == '"public"."AnotherThing"'
    AnotherThing.validate_name()

    assert DealFruitFunWithName.fq() == FQTuple("public", "DealFruitFun", "name text")
    assert MaterializedThing.fqdeps_on() == {FQTuple("public", "AnotherThing")}

    with get_cursor(args) as cursor:
        assert DealFruitFunWithName.sign(cursor) != DealFruitFun.sign(cursor)
    # "Sidekicks" generates
    MaterializedThing.sidekicks()

    # We can also add dependencies on different objects as triggers for
    # A materialized view


def test_create_view():
    args = ArgType(txdiscipline="jumbo")

    # What are the dependencies of `MaterializedThing`?
    with get_cursor(args) as cursor:
        cursor.execute(fruittable_SQL)

    cmd_sync(args)

    with get_cursor(args) as cursor:
        cursor.execute(f"SELECT * FROM {AnotherThing.db_object_identity()};")
        cursor.fetchall()

    # All dbszmizdats should be registered now

    samizdats = tuple(depsort_with_sidekicks(sanity_check(get_samizdats())))

    dot(samizdats)

    with get_cursor(args) as cursor:
        current_state = get_dbstate(cursor)
        (dbinfo_to_class(s) for s in current_state)
        get_dbstate(cursor)
        # We've just done a sync so dbstate should equal defined state
        assert dbstate_equals_definedstate(cursor, samizdats).issame

    cmd_sync(args)
    with get_cursor(args) as cursor:
        assert DealFruitFunWithName.sign(cursor) != DealFruitFun.sign(cursor)
        cursor.execute(
            f"""
            SELECT "{DealFruitFunWithName.get_name()}"(name) AS treat FROM "public"."Pet"
        """
        )
    cmd_nuke(args)
    with get_cursor(args) as cursor:
        # Now we expect this to raise an error
        with pytest.raises(Exception):
            cursor.execute(f"SELECT * FROM {AnotherThing.db_object_identity()};")
            cursor.fetchall()


def test_long_name_raises():
    """
    Samizdats with 'broken' names are not allowed
    """
    args = ArgType(txdiscipline="jumbo")

    class LongNamedSamizdat(SamizdatView):
        object_name = "hello" * 60
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    cmd_nuke(args)
    with pytest.raises(UnsuitableNameError):
        cmd_sync(args, [LongNamedSamizdat])


def test_unsuitable_name_raises():
    args = ArgType(txdiscipline="jumbo")

    class BadlyNamedSamizdat(SamizdatView):
        object_name = '"hello"'
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    cmd_nuke(args)
    with pytest.raises(UnsuitableNameError):
        cmd_sync(args, [BadlyNamedSamizdat])


def test_duplicate_name_raises():
    args = ArgType(txdiscipline="jumbo")

    class IAmCalledHello(SamizdatView):
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    class IAmCalledHelloToo(SamizdatView):
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    cmd_nuke(args)
    with pytest.raises(NameClashError):
        cmd_sync(args, [IAmCalledHello, IAmCalledHelloToo])


def test_cyclic_exception():
    args = ArgType(txdiscipline="jumbo")

    class helloWorld(SamizdatView):
        deps_on = {"hello2"}
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    class helloWorldAgain(SamizdatView):
        deps_on = {"hello"}
        object_name = "hello2"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    cmd_nuke(args)
    with pytest.raises(DependencyCycleError):
        cmd_sync(args, [helloWorld, helloWorldAgain])


def test_self_reference_raises():
    """
    A Samizdat may not refer to itself as a dependency
    """
    args = ArgType(txdiscipline="jumbo")

    class hello(SamizdatView):
        deps_on = {"hello"}
        object_name = "hello"
        sql_template = """
            ${preamble}
            SELECT now();
            ${postamble}
        """

    cmd_nuke(args)
    with pytest.raises(DependencyCycleError):
        cmd_sync(args, [hello])


def test_sidekicks():
    """
    This test ensures that a materialized view
    with "refresh triggers" watches for changes
    """

    args = ArgType(txdiscipline="jumbo")
    cmd_nuke(args)

    class Treater(SamizdatMaterializedView):
        deps_on_unmanaged = {"d", "d2"}
        refresh_triggers = {"d", "d2"}
        sql_template = """
            ${preamble}
            SELECT * FROM d UNION SELECT * FROM d2
            ${postamble};
        """

    # The "sidekicks" should be included in the detected samizdats
    # This should be one 'refresh' and two 'triggers'
    assert len(depsort_with_sidekicks([Treater])) == 4

    with get_cursor(args) as c:
        c.execute("DROP TABLE IF EXISTS d CASCADE;")
        c.execute("DROP TABLE IF EXISTS d2 CASCADE;")
        c.execute("CREATE TABLE IF NOT EXISTS d AS SELECT now() n;")
        c.execute("COMMIT;")
        c.execute("CREATE TABLE IF NOT EXISTS d2 AS SELECT now() n;")
        c.execute("COMMIT;")

    # When cmd_sync is run, because this MatView has `refresh triggers`
    # the view will be refreshed on every insert / update / truncate to d or d2

    cmd_sync(args, [Treater])

    with get_cursor(args) as c:
        c.execute("""SELECT * FROM public."Treater" """)
        vals = c.fetchall()
        assert len(vals) == 2

    # Add a value to one of the "watched" tables. The
    # materialized view should refresh.
    with get_cursor(args) as c:
        c.execute("INSERT INTO d SELECT now();")
        c.execute("COMMIT;")
        c.execute("""SELECT * FROM public."Treater" """)
        vals = c.fetchall()
        assert len(vals) == 3

    with get_cursor(args) as c:
        c.execute("DROP TABLE IF EXISTS d CASCADE;")
        c.execute("DROP TABLE IF EXISTS d2 CASCADE;")

    cmd_nuke(args)
