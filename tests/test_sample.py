# content of test_sample.py
import os
from dotenv import load_dotenv
import psycopg

import pytest
from dbsamizdat.libdb import dbinfo_to_class, dbstate_equals_definedstate, get_dbstate
from dbsamizdat.libgraph import depsort_with_sidekicks, sanity_check
from dbsamizdat.loader import get_samizdats
from dbsamizdat.runner import ArgType, cmd_nuke, cmd_sync, get_cursor

from dbsamizdat.graphvizdot import dot

from dbsamizdat.samizdat import SamizdatMaterializedView, SamizdatView
from dbsamizdat.samtypes import FQTuple
from dbsamizdat.test_samizdats import DealFruitFun, DealFruitFunWithName
from dbsamizdat.util import db_object_identity

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
    # AnotherThing.fqify()
    AnotherThing.fqdeps_on()
    AnotherThing.fqdeps_on_unmanaged()
    AnotherThing.dbinfo()
    # These SQL-generating functions require a cursor
    with psycopg.connect(DEFAULT_URL).cursor() as c:
        AnotherThing.sign(c)

    AnotherThing.create()
    AnotherThing.drop()

    AnotherThing.and_sidekicks()
    AnotherThing.head_id()

    assert AnotherThing.schema == "public"
    assert AnotherThing.get_name() == "AnotherThing"
    assert AnotherThing.db_object_identity() == '"public"."AnotherThing"'
    AnotherThing.validate_name()

    assert DealFruitFunWithName.fq() == FQTuple("public", "DealFruitFun", "name text")
    assert MaterializedThing.fqdeps_on() == {FQTuple("public", "AnotherThing")}

    args = ArgType(txdiscipline="jumbo")

    db_object_identity(DealFruitFunWithName)
    assert DealFruitFunWithName.sign(get_cursor(args)) != DealFruitFun.sign(
        get_cursor(args)
    )


def test_create_view():
    args = ArgType(txdiscipline="jumbo")

    # What are the dependencies of `MaterializedThing`?
    cursor = get_cursor(args)
    cursor.execute(fruittable_SQL)
    cursor.execute("COMMIT;")
    cursor.close()

    cmd_sync(args)
    cursor = get_cursor(args)
    cursor.execute(f"SELECT * FROM {AnotherThing.db_object_identity()};")
    cursor.fetchall()
    cursor.close()

    # All dbszmizdats should be registered now

    samizdats = depsort_with_sidekicks(sanity_check(get_samizdats()))

    dot(samizdats)

    cursor = get_cursor(args)

    current_state = get_dbstate(cursor)
    (dbinfo_to_class(s) for s in current_state)

    try:
        get_dbstate(cursor)
        # We've just done a sync so dbstate should equal defined state
        assert dbstate_equals_definedstate(cursor, samizdats).issame
    finally:
        cursor.close()

    cmd_sync(args)
    cmd_nuke(args)
    cursor = get_cursor(args)
    # Now we expect this to raise an error
    with pytest.raises(Exception):
        cursor.execute(f"SELECT * FROM {AnotherThing.db_object_identity()};")
        cursor.fetchall()
    cursor.close()
