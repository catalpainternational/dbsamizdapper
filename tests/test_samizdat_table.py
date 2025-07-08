"""
Tests for the SamizdatTable type
"""
import os
import pytest
from dotenv import load_dotenv

from dbsamizdat.exceptions import UnsuitableNameError, NameClashError
from dbsamizdat.libdb import dbstate_equals_definedstate, get_dbstate
from dbsamizdat.libgraph import depsort_with_sidekicks, sanity_check
from dbsamizdat.runner import ArgType, cmd_nuke, cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatTable, SamizdatView, SamizdatMaterializedView
from dbsamizdat.samtypes import FQTuple, entitypes

load_dotenv()
args = ArgType(
    txdiscipline="jumbo", 
    verbosity=3, 
    dburl=os.environ.get("DBURL", "postgresql://postgres@localhost:5435/postgres")
)


class SimpleTable(SamizdatTable):
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
    deps_on = {SimpleTable}
    sql_template = f"""
        ${{preamble}}
        SELECT name, created_at FROM {SimpleTable.db_object_identity()}
        WHERE created_at > NOW() - INTERVAL '1 day'
        ${{postamble}}
    """


class MaterializedViewDependingOnTable(SamizdatMaterializedView):
    deps_on = {SimpleTable}
    sql_template = f"""
        ${{preamble}}
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT name) as unique_names
        FROM {SimpleTable.db_object_identity()}
        ${{postamble}}
    """


def test_samizdat_table_basic_properties():
    """Test basic properties of SamizdatTable"""
    assert SimpleTable.entity_type == entitypes.TABLE
    assert SimpleTable.schema == "public"
    assert SimpleTable.get_name() == "SimpleTable"
    assert SimpleTable.db_object_identity() == '"public"."SimpleTable"'
    assert SimpleTable.fq() == FQTuple("public", "SimpleTable")


def test_samizdat_table_validation():
    """Test that SamizdatTable validates names properly"""
    SimpleTable.validate_name()  # Should not raise
    
    # Test with invalid name
    class BadNameTable(SamizdatTable):
        object_name = "hello" * 60  # Too long
        sql_template = """
            ${preamble}
            (id INTEGER)
            ${postamble}
        """
    
    with pytest.raises(UnsuitableNameError):
        BadNameTable.validate_name()


def test_samizdat_table_sql_generation():
    """Test SQL generation for tables"""
    create_sql = SimpleTable.create()
    
    # Should contain CREATE TABLE
    assert "CREATE TABLE" in create_sql
    assert SimpleTable.db_object_identity() in create_sql
    assert "id SERIAL PRIMARY KEY" in create_sql
    assert "name VARCHAR(100) NOT NULL" in create_sql
    
    # Test drop SQL
    drop_sql = SimpleTable.drop()
    assert "DROP TABLE" in drop_sql
    assert SimpleTable.db_object_identity() in drop_sql
    assert "CASCADE" in drop_sql


def test_samizdat_table_with_constraints():
    """Test table with various constraints"""
    create_sql = TableWithConstraints.create()
    
    assert "email VARCHAR(255) UNIQUE NOT NULL" in create_sql
    assert "age INTEGER CHECK (age >= 0)" in create_sql
    assert "DEFAULT 'Unknown'" in create_sql


def test_samizdat_table_dependencies():
    """Test dependency handling with tables"""
    # Tables should not have dependencies by default
    assert SimpleTable.fqdeps_on() == set()
    assert SimpleTable.fqdeps_on_unmanaged() == set()
    
    # Views depending on tables should work
    assert ViewDependingOnTable.fqdeps_on() == {SimpleTable.fq()}
    assert MaterializedViewDependingOnTable.fqdeps_on() == {SimpleTable.fq()}


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


def test_samizdat_table_create_and_drop():
    """Test creating and dropping tables in the database"""
    cmd_nuke(args)
    
    # Create the table
    cmd_sync(args, [SimpleTable])
    
    # Verify it exists
    with get_cursor(args) as cursor:
        cursor.execute(f"SELECT * FROM {SimpleTable.db_object_identity()}")
        # Should not raise an error
        
        # Test the table structure
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'SimpleTable' 
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        # Check expected columns exist
        column_names = [col[0] for col in columns]
        assert 'id' in column_names
        assert 'name' in column_names
        assert 'created_at' in column_names
    
    # Clean up
    cmd_nuke(args)
    


def test_samizdat_table_with_dependencies():
    """Test table creation with dependent views"""
    cmd_nuke(args)
    
    # Create table and dependent view
    samizdats = [SimpleTable, ViewDependingOnTable]
    cmd_sync(args, samizdats)
    
    with get_cursor(args) as cursor:
        # Verify table exists
        cursor.execute(f"SELECT * FROM {SimpleTable.db_object_identity()}")
        
        # Verify view exists and works
        cursor.execute(f"SELECT * FROM {ViewDependingOnTable.db_object_identity()}")
        
        # Insert some data to test the view
        cursor.execute(f"""
            INSERT INTO {SimpleTable.db_object_identity()} (name) 
            VALUES ('test1'), ('test2')
        """)
        
        # Query the view
        cursor.execute(f"SELECT COUNT(*) FROM {ViewDependingOnTable.db_object_identity()}")
        count = cursor.fetchone()[0]
        assert count == 2
    
    cmd_nuke(args)


def test_samizdat_table_dependency_order():
    """Test that tables are created before dependent objects"""
    cmd_nuke(args)
    
    samizdats = [SimpleTable, ViewDependingOnTable, MaterializedViewDependingOnTable]
    sanity_check(samizdats)
    sorted_samizdats = depsort_with_sidekicks(samizdats)
    
    # Table should come first
    sorted_names = [s.get_name() for s in sorted_samizdats]
    table_index = sorted_names.index('SimpleTable')
    view_index = sorted_names.index('ViewDependingOnTable')
    matview_index = sorted_names.index('MaterializedViewDependingOnTable')
    
    assert table_index < view_index
    assert table_index < matview_index


def test_samizdat_table_state_tracking():
    """Test that table state is properly tracked"""
    cmd_nuke(args)
    
    # Create table
    cmd_sync(args, [SimpleTable])
    
    with get_cursor(args) as cursor:
        # Check that state tracking works
        current_state = list(get_dbstate(cursor))
        assert len(current_state) > 0
        
        # Verify our table is in the state
        table_found = False
        for state_item in current_state:
            if state_item.viewname == 'SimpleTable' and state_item.objecttype == 'TABLE':
                table_found = True
                break
        
        assert table_found, "Table not found in database state"
        
        # Test state comparison
        result = dbstate_equals_definedstate(cursor, [SimpleTable])
        assert result.issame
    
    cmd_nuke(args)


def test_samizdat_table_name_clashes():
    """Test that name clashes are detected"""
    class DuplicateTable1(SamizdatTable):
        object_name = "duplicate_name"
        sql_template = """
            ${preamble}
            (id INTEGER)
            ${postamble}
        """
    
    class DuplicateTable2(SamizdatTable):
        object_name = "duplicate_name"
        sql_template = """
            ${preamble}
            (id INTEGER)
            ${postamble}
        """
    
    cmd_nuke(args)
    with pytest.raises(NameClashError):
        cmd_sync(args, [DuplicateTable1, DuplicateTable2])


def test_samizdat_table_custom_schema():
    """
    Test table creation in custom schema
    Note that before running this test, you need to create the schema
    outside of the test infrastructure.
    
    """
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
    
    cmd_nuke(args)

    try:
        cmd_sync(args, [CustomSchemaTable])
    except Exception as e:
        print(e)
    
        with get_cursor(args) as cursor:
            # Verify table exists in custom schema
            cursor.execute(f"SELECT * FROM {CustomSchemaTable.db_object_identity()}")
            
            # Verify it's in the right schema
            cursor.execute("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_name = 'CustomSchemaTable'
            """)
            result = cursor.fetchone()
            assert result[0] == 'test_schema'
            assert result[1] == 'CustomSchemaTable'
    
    finally:
        cmd_nuke(args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 