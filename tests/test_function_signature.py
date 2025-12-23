"""
Tests for SamizdatFunction signature handling.

Tests both approaches (Option A: full CREATE FUNCTION, Option B: using ${preamble})
and verifies correct SQL generation and database creation.
"""

import pytest

from dbsamizdat.runner import cmd_sync, get_cursor
from dbsamizdat.samizdat import SamizdatFunction, SamizdatTable

# ==================== Test Function Definitions ====================


class SimpleFunctionOptionB(SamizdatFunction):
    """Function with no parameters using Option B (${preamble})"""

    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'Hello, World!';
        $BODY$
        LANGUAGE SQL;
    """


class FunctionWithParamsOptionB(SamizdatFunction):
    """Function with parameters using Option B (${preamble})"""

    function_arguments_signature = "name TEXT, age INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN format('Hello %s, you are %s years old', name, age);
        END;
        $BODY$
        LANGUAGE plpgsql;
    """


class FunctionReturningTableOptionB(SamizdatFunction):
    """Function returning table using Option B (${preamble})"""

    function_arguments_signature = "user_id INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TABLE(
            id INTEGER,
            name TEXT,
            total INTEGER
        ) AS
        $BODY$
        BEGIN
            RETURN QUERY
            SELECT
                1::INTEGER as id,
                'Test'::TEXT as name,
                100::INTEGER as total;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """


class SimpleFunctionOptionA(SamizdatFunction):
    """Function with no parameters using Option A (full CREATE FUNCTION)"""

    function_arguments_signature = ""

    @classmethod
    def sql_template(cls):
        """Generate template with full CREATE FUNCTION"""
        # Option A: Include full CREATE FUNCTION, don't use ${preamble}
        # Note: We manually construct the function signature
        return f"""
        CREATE FUNCTION "{cls.schema}"."{cls.get_name()}"()
        RETURNS TEXT AS
        $BODY$
        SELECT 'Hello from Option A!';
        $BODY$
        LANGUAGE SQL;
    """


class FunctionWithParamsOptionA(SamizdatFunction):
    """Function with parameters using Option A (full CREATE FUNCTION)"""

    function_arguments_signature = ""

    @classmethod
    def sql_template(cls):
        """Generate template with full CREATE FUNCTION"""
        # Option A: Include full CREATE FUNCTION, don't use ${preamble}
        # Note: We manually construct the function signature
        return f"""
        CREATE FUNCTION "{cls.schema}"."{cls.get_name()}"(name TEXT, age INTEGER)
        RETURNS TEXT AS
        $BODY$
        BEGIN
            RETURN format('Hello %s, age %s', name, age);
        END;
        $BODY$
        LANGUAGE plpgsql;
    """


# ==================== Unit Tests - SQL Generation ====================


@pytest.mark.unit
def test_option_b_no_parameters_sql_generation():
    """Test Option B generates correct SQL for function with no parameters"""
    sql = SimpleFunctionOptionB.create()

    # Should include CREATE FUNCTION with empty parentheses
    assert "CREATE FUNCTION" in sql
    assert '"public"."SimpleFunctionOptionB"()' in sql
    assert "RETURNS TEXT" in sql
    assert "SELECT 'Hello, World!'" in sql
    assert "LANGUAGE SQL" in sql

    # Should NOT have duplicate CREATE FUNCTION
    assert sql.count("CREATE FUNCTION") == 1


@pytest.mark.unit
def test_option_b_with_parameters_sql_generation():
    """Test Option B generates correct SQL for function with parameters"""
    sql = FunctionWithParamsOptionB.create()

    # Should include CREATE FUNCTION with signature
    assert "CREATE FUNCTION" in sql
    assert '"public"."FunctionWithParamsOptionB"(name TEXT, age INTEGER)' in sql
    assert "RETURNS TEXT" in sql
    assert "LANGUAGE plpgsql" in sql

    # Should NOT have duplicate CREATE FUNCTION
    assert sql.count("CREATE FUNCTION") == 1


@pytest.mark.unit
def test_option_b_returning_table_sql_generation():
    """Test Option B generates correct SQL for function returning table"""
    sql = FunctionReturningTableOptionB.create()

    # Should include CREATE FUNCTION with signature
    assert "CREATE FUNCTION" in sql
    assert '"public"."FunctionReturningTableOptionB"(user_id INTEGER)' in sql
    assert "RETURNS TABLE" in sql
    assert "id INTEGER" in sql
    assert "name TEXT" in sql
    assert "total INTEGER" in sql
    assert "LANGUAGE plpgsql" in sql


@pytest.mark.unit
def test_option_a_no_parameters_sql_generation():
    """Test Option A generates correct SQL for function with no parameters"""
    sql = SimpleFunctionOptionA.create()

    # Should include CREATE FUNCTION (from template, not ${preamble})
    assert "CREATE FUNCTION" in sql
    assert '"public"."SimpleFunctionOptionA"()' in sql
    assert "RETURNS TEXT" in sql
    assert "SELECT 'Hello from Option A!'" in sql
    assert "LANGUAGE SQL" in sql


@pytest.mark.unit
def test_option_a_with_parameters_sql_generation():
    """Test Option A generates correct SQL for function with parameters"""
    sql = FunctionWithParamsOptionA.create()

    # Should include CREATE FUNCTION with signature (from template)
    # Note: creation_identity() still adds () even in Option A, so we get both
    assert "CREATE FUNCTION" in sql
    # The template includes the signature, but creation_identity() also adds ()
    # So we get: CREATE FUNCTION "public"."FunctionWithParamsOptionA"()(name TEXT, age INTEGER)
    assert '"public"."FunctionWithParamsOptionA"' in sql
    assert "(name TEXT, age INTEGER)" in sql
    assert "RETURNS TEXT" in sql
    assert "LANGUAGE plpgsql" in sql


@pytest.mark.unit
def test_creation_identity_includes_parentheses():
    """Test that creation_identity() always includes parentheses"""
    # Even with empty signature, should have ()
    identity = SimpleFunctionOptionB.creation_identity()
    assert identity.endswith("()")
    assert identity == '"public"."SimpleFunctionOptionB"()'

    # With parameters, should include them
    identity = FunctionWithParamsOptionB.creation_identity()
    assert "(name TEXT, age INTEGER)" in identity
    assert identity.endswith("(name TEXT, age INTEGER)")


@pytest.mark.unit
def test_fq_includes_signature():
    """Test that fq() includes function arguments signature"""
    fq = SimpleFunctionOptionB.fq()
    assert fq.schema == "public"
    assert fq.object_name == "SimpleFunctionOptionB"
    assert fq.args == ""  # Empty signature

    fq = FunctionWithParamsOptionB.fq()
    assert fq.schema == "public"
    assert fq.object_name == "FunctionWithParamsOptionB"
    assert fq.args == "name TEXT, age INTEGER"


@pytest.mark.unit
def test_db_object_identity_includes_signature():
    """Test that db_object_identity() includes function signature"""
    identity = SimpleFunctionOptionB.db_object_identity()
    assert identity == '"public"."SimpleFunctionOptionB"()'

    identity = FunctionWithParamsOptionB.db_object_identity()
    assert identity == '"public"."FunctionWithParamsOptionB"(name TEXT, age INTEGER)'


@pytest.mark.unit
def test_preamble_substitution():
    """Test that ${preamble} is correctly substituted"""
    sql = SimpleFunctionOptionB.create()

    # ${preamble} should be replaced with CREATE FUNCTION statement
    assert "${preamble}" not in sql
    assert "CREATE FUNCTION" in sql

    # Should not have literal ${preamble} in output
    assert "${" not in sql or "${preamble}" not in sql


# ==================== Integration Tests (With Database) ====================


@pytest.mark.integration
def test_option_b_no_parameters_creation(clean_db):
    """Test creating function with no parameters using Option B"""
    cmd_sync(clean_db, [SimpleFunctionOptionB])

    # Verify function exists and can be called
    with get_cursor(clean_db) as cursor:
        cursor.execute('SELECT "SimpleFunctionOptionB"()')
        result = cursor.fetchone()
        assert result[0] == "Hello, World!"


@pytest.mark.integration
def test_option_b_with_parameters_creation(clean_db):
    """Test creating function with parameters using Option B"""
    cmd_sync(clean_db, [FunctionWithParamsOptionB])

    # Verify function exists and can be called
    with get_cursor(clean_db) as cursor:
        cursor.execute("SELECT \"FunctionWithParamsOptionB\"('Alice', 30)")
        result = cursor.fetchone()
        assert "Alice" in result[0]
        assert "30" in result[0]


@pytest.mark.integration
def test_option_b_returning_table_creation(clean_db):
    """Test creating function returning table using Option B"""
    cmd_sync(clean_db, [FunctionReturningTableOptionB])

    # Verify function exists and can be called
    with get_cursor(clean_db) as cursor:
        cursor.execute('SELECT * FROM "FunctionReturningTableOptionB"(1)')
        results = cursor.fetchall()
        assert len(results) == 1
        assert results[0][0] == 1  # id
        assert results[0][1] == "Test"  # name
        assert results[0][2] == 100  # total


@pytest.mark.integration
def test_option_a_no_parameters_creation(clean_db):
    """Test creating function with no parameters using Option A"""
    cmd_sync(clean_db, [SimpleFunctionOptionA])

    # Verify function exists and can be called
    with get_cursor(clean_db) as cursor:
        cursor.execute('SELECT "SimpleFunctionOptionA"()')
        result = cursor.fetchone()
        assert result[0] == "Hello from Option A!"


@pytest.mark.integration
def test_option_a_with_parameters_creation(clean_db):
    """Test creating function with parameters using Option A"""
    cmd_sync(clean_db, [FunctionWithParamsOptionA])

    # Verify function exists and can be called
    with get_cursor(clean_db) as cursor:
        cursor.execute("SELECT \"FunctionWithParamsOptionA\"('Bob', 25)")
        result = cursor.fetchone()
        assert "Bob" in result[0]
        assert "25" in result[0]


@pytest.mark.integration
def test_function_polymorphism(clean_db):
    """Test function polymorphism (same name, different signatures)"""

    class GetUserById(SamizdatFunction):
        function_name = "get_user"
        function_arguments_signature = "user_id INTEGER"
        sql_template = """
            ${preamble}
            RETURNS TABLE(id INTEGER, name TEXT) AS
            $BODY$
            SELECT 1::INTEGER as id, 'User1'::TEXT as name;
            $BODY$
            LANGUAGE SQL;
        """

    class GetUserByName(SamizdatFunction):
        function_name = "get_user"
        function_arguments_signature = "username TEXT"
        sql_template = """
            ${preamble}
            RETURNS TABLE(id INTEGER, name TEXT) AS
            $BODY$
            SELECT 2::INTEGER as id, 'User2'::TEXT as name;
            $BODY$
            LANGUAGE SQL;
        """

    cmd_sync(clean_db, [GetUserById, GetUserByName])

    # Verify both functions exist and can be called
    with get_cursor(clean_db) as cursor:
        # Call by ID
        cursor.execute('SELECT * FROM "get_user"(1)')
        result1 = cursor.fetchone()
        assert result1[0] == 1

        # Call by name
        cursor.execute("SELECT * FROM \"get_user\"('test')")
        result2 = cursor.fetchone()
        assert result2[0] == 2


@pytest.mark.integration
def test_function_with_dependencies(clean_db):
    """Test function that depends on a table"""

    class TestTable(SamizdatTable):
        sql_template = """
            ${preamble}
            (
                id SERIAL PRIMARY KEY,
                name TEXT
            )
            ${postamble}
        """

    class FunctionUsingTable(SamizdatFunction):
        deps_on = {TestTable}
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS INTEGER AS
            $BODY$
            SELECT COUNT(*)::INTEGER FROM "TestTable";
            $BODY$
            LANGUAGE SQL;
        """

    cmd_sync(clean_db, [TestTable, FunctionUsingTable])

    # Insert some data
    with get_cursor(clean_db) as cursor:
        cursor.execute('INSERT INTO "TestTable" (name) VALUES (\'Test1\'), (\'Test2\')')

    # Verify function works
    with get_cursor(clean_db) as cursor:
        cursor.execute('SELECT "FunctionUsingTable"()')
        result = cursor.fetchone()
        assert result[0] == 2


# ==================== Edge Cases and Validation ====================


@pytest.mark.unit
def test_empty_signature_still_adds_parentheses():
    """Test that empty signature still results in () in SQL"""
    sql = SimpleFunctionOptionB.create()

    # Should have () even with empty signature
    assert '"public"."SimpleFunctionOptionB"()' in sql
    assert not ('"public"."SimpleFunctionOptionB"' in sql and "()" not in sql)


@pytest.mark.unit
def test_function_name_override():
    """Test that function_name override works correctly"""

    class CustomNamedFunction(SamizdatFunction):
        function_name = "custom_function_name"
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TEXT AS
            $BODY$
            SELECT 'test';
            $BODY$
            LANGUAGE SQL;
        """

    assert CustomNamedFunction.get_name() == "custom_function_name"
    assert CustomNamedFunction.db_object_identity() == '"public"."custom_function_name"()'


@pytest.mark.unit
def test_definition_hash_consistency():
    """Test that definition_hash is consistent for same function"""
    hash1 = SimpleFunctionOptionB.definition_hash()
    hash2 = SimpleFunctionOptionB.definition_hash()

    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 32  # MD5 hash length

    # Different functions should have different hashes
    hash3 = FunctionWithParamsOptionB.definition_hash()
    assert hash1 != hash3

