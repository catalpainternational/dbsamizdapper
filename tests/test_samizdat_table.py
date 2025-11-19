"""Tests for the SamizdatTable type"""

import pytest

from dbsamizdat.exceptions import NameClashError, UnsuitableNameError
from dbsamizdat.libdb import dbstate_equals_definedstate, get_dbstate
from dbsamizdat.libgraph import sanity_check
from dbsamizdat.runner import cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatMaterializedView, SamizdatTable, SamizdatView
from dbsamizdat.samtypes import FQTuple, entitypes

# ==================== Test Table Definitions ====================


class SimpleTable(SamizdatTable):
    """Basic table for testing"""

    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """


class TableWithConstraints(SamizdatTable):
    """Table with various constraints"""

    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            age INTEGER CHECK (age >= 0),
            department VARCHAR(50) DEFAULT 'Unknown'
        )
        ${postamble}
    """


class ViewDependingOnTable(SamizdatView):
    """View that depends on SimpleTable"""

    deps_on = {SimpleTable}
    sql_template = f"""
        ${{preamble}}
        SELECT name, created_at FROM {SimpleTable.db_object_identity()}
        WHERE created_at > NOW() - INTERVAL '1 day'
        ${{postamble}}
    """


class MaterializedViewDependingOnTable(SamizdatMaterializedView):
    """Materialized view that depends on SimpleTable"""

    deps_on = {SimpleTable}
    sql_template = f"""
        ${{preamble}}
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT name) as unique_names
        FROM {SimpleTable.db_object_identity()}
        ${{postamble}}
    """


# ==================== Unit Tests (No Database) ====================


@pytest.mark.unit
def test_samizdat_table_basic_properties():
    """Test basic properties of SamizdatTable"""
    assert SimpleTable.entity_type == entitypes.TABLE
    assert SimpleTable.schema == "public"
    assert SimpleTable.get_name() == "SimpleTable"
    assert SimpleTable.db_object_identity() == '"public"."SimpleTable"'
    assert SimpleTable.fq() == FQTuple("public", "SimpleTable")


@pytest.mark.unit
def test_samizdat_table_validation():
    """Test that SamizdatTable validates names properly"""
    # Valid name should not raise
    SimpleTable.validate_name()

    # Invalid name should raise
    class BadNameTable(SamizdatTable):
        object_name = "hello" * 60  # Too long
        sql_template = """
            ${preamble}
            (id INTEGER)
            ${postamble}
        """

    with pytest.raises(UnsuitableNameError):
        BadNameTable.validate_name()


@pytest.mark.unit
def test_samizdat_table_sql_generation():
    """Test SQL generation for tables"""
    create_sql = SimpleTable.create()

    # Should contain CREATE TABLE (not UNLOGGED by default)
    assert "CREATE TABLE" in create_sql
    assert "UNLOGGED" not in create_sql, "Default tables should not be UNLOGGED"
    assert SimpleTable.db_object_identity() in create_sql
    assert "id SERIAL PRIMARY KEY" in create_sql
    assert "name VARCHAR(100) NOT NULL" in create_sql

    # Test drop SQL
    drop_sql = SimpleTable.drop()
    assert "DROP TABLE" in drop_sql
    assert SimpleTable.db_object_identity() in drop_sql
    assert "CASCADE" in drop_sql


@pytest.mark.unit
def test_samizdat_table_with_constraints():
    """Test table with various constraints"""
    create_sql = TableWithConstraints.create()

    assert "email VARCHAR(255) UNIQUE NOT NULL" in create_sql
    assert "age INTEGER CHECK (age >= 0)" in create_sql
    assert "DEFAULT 'Unknown'" in create_sql


@pytest.mark.unit
def test_samizdat_table_dependencies():
    """Test dependency handling with tables"""
    # Tables should not have dependencies by default
    assert SimpleTable.fqdeps_on() == set()
    assert SimpleTable.fqdeps_on_unmanaged() == set()

    # Views depending on tables should work
    assert ViewDependingOnTable.fqdeps_on() == {SimpleTable.fq()}
    assert MaterializedViewDependingOnTable.fqdeps_on() == {SimpleTable.fq()}


@pytest.mark.unit
def test_samizdat_table_definition_hash():
    """Test that tables generate proper definition hashes"""
    hash1 = SimpleTable.definition_hash()
    hash2 = SimpleTable.definition_hash()

    # Should be consistent
    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 32  # MD5 hash length

    # Different tables should have different hashes
    hash3 = TableWithConstraints.definition_hash()
    assert hash1 != hash3


@pytest.mark.unit
def test_samizdat_table_dbinfo():
    """Test database info generation"""
    dbinfo = SimpleTable.dbinfo()

    # Should be valid JSON
    import json

    parsed = json.loads(dbinfo)

    assert "dbsamizdat" in parsed
    assert "version" in parsed["dbsamizdat"]
    assert "created" in parsed["dbsamizdat"]
    assert "definition_hash" in parsed["dbsamizdat"]


# ==================== Integration Tests (With Database) ====================


@pytest.mark.integration
def test_samizdat_table_create_and_drop(clean_db):
    """Test creating and dropping tables in the database"""
    # Create the table
    cmd_sync(clean_db, [SimpleTable])

    # Verify it exists and has correct structure
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {SimpleTable.db_object_identity()}")
        # Should not raise an error

        # Test the table structure
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'SimpleTable'
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        )
        columns = cursor.fetchall()

        # Check expected columns exist
        column_names = [col[0] for col in columns]
        assert "id" in column_names
        assert "name" in column_names
        assert "created_at" in column_names


@pytest.mark.integration
def test_samizdat_table_with_dependencies(clean_db):
    """Test table creation with dependent views"""
    # Create table and dependent view
    cmd_sync(clean_db, [SimpleTable, ViewDependingOnTable])

    # Verify both exist
    with get_cursor(clean_db) as cursor:
        # Table should exist
        cursor.execute(f"SELECT * FROM {SimpleTable.db_object_identity()}")

        # View should exist
        cursor.execute(f"SELECT * FROM {ViewDependingOnTable.db_object_identity()}")


@pytest.mark.integration
def test_samizdat_table_dependency_order(clean_db):
    """Test that tables are created in correct dependency order"""

    class Table1(SamizdatTable):
        sql_template = """
            ${preamble}
            (id SERIAL PRIMARY KEY, data TEXT)
            ${postamble}
        """

    class Table2(SamizdatTable):
        deps_on = {Table1}
        sql_template = f"""
            ${{preamble}}
            (
                id SERIAL PRIMARY KEY,
                table1_id INTEGER REFERENCES {Table1.db_object_identity()}(id),
                value TEXT
            )
            ${{postamble}}
        """

    class ViewOnBoth(SamizdatView):
        deps_on = {Table1, Table2}
        sql_template = f"""
            ${{preamble}}
            SELECT t1.data, t2.value
            FROM {Table1.db_object_identity()} t1
            JOIN {Table2.db_object_identity()} t2 ON t2.table1_id = t1.id
            ${{postamble}}
        """

    # Sync should handle dependency order automatically
    cmd_sync(clean_db, [Table1, Table2, ViewOnBoth])

    # Verify all exist
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {Table1.db_object_identity()}")
        cursor.execute(f"SELECT * FROM {Table2.db_object_identity()}")
        cursor.execute(f"SELECT * FROM {ViewOnBoth.db_object_identity()}")


@pytest.mark.integration
def test_samizdat_table_state_tracking(clean_db):
    """Test that table state is properly tracked"""
    # Create table
    cmd_sync(clean_db, [SimpleTable])

    # Check database state
    with get_cursor(clean_db) as cursor:
        db_state = get_dbstate(cursor)

        # SimpleTable should be in database state
        table_found = False
        for state_item in db_state:
            if state_item[0] == "public" and state_item[1] == "SimpleTable":
                table_found = True
                break

        assert table_found, "Table not found in database state"

        # Test state comparison
        result = dbstate_equals_definedstate(cursor, [SimpleTable])
        assert result.issame


@pytest.mark.integration
def test_samizdat_table_unlogged(clean_db):
    """Test that unlogged tables are created correctly"""

    class UnloggedTable(SamizdatTable):
        unlogged = True
        sql_template = """
            ${preamble}
            (
                id SERIAL PRIMARY KEY,
                data TEXT
            )
            ${postamble}
        """

    # Verify SQL contains UNLOGGED
    create_sql = UnloggedTable.create()
    assert "UNLOGGED" in create_sql, "Should create UNLOGGED table"

    # Create and verify
    cmd_sync(clean_db, [UnloggedTable])

    # Verify table exists
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {UnloggedTable.db_object_identity()}")


@pytest.mark.integration
def test_samizdat_table_name_clashes(clean_db):
    """Test that name clashes are detected"""

    class DuplicateTable1(SamizdatTable):
        object_name = "duplicate_name"
        sql_template = """
            ${preamble}
            (id INTEGER)
            ${postamble}
        """

    class DuplicateTable2(SamizdatTable):
        object_name = "duplicate_name"  # Same name!
        sql_template = """
            ${preamble}
            (value TEXT)
            ${postamble}
        """

    with pytest.raises(NameClashError):
        # Should detect duplicate names
        sanity_check({DuplicateTable1, DuplicateTable2})


@pytest.mark.integration
@pytest.mark.requires_schema
def test_samizdat_table_custom_schema(clean_db, test_schema):
    """Test table creation in custom schema"""

    class CustomSchemaTable(SamizdatTable):
        schema = "test_schema"
        sql_template = """
            ${preamble}
            (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
            ${postamble}
        """

    # Create table in custom schema
    cmd_sync(clean_db, [CustomSchemaTable])

    # Verify table exists in custom schema
    with get_cursor(clean_db) as cursor:
        cursor.execute(f"SELECT * FROM {CustomSchemaTable.db_object_identity()}")
        # Should not raise

        # Verify schema
        cursor.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name = 'CustomSchemaTable'
        """
        )
        result = cursor.fetchall()
        assert len(result) == 1
        assert result[0][0] == "test_schema"
