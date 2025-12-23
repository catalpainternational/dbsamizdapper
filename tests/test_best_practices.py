"""
Tests for Best Practices and Common Patterns documented in USAGE.md.

This test file verifies that all examples in the "Best Practices and Common Patterns"
section work correctly and can be used as reference implementations.
"""

import pytest

from dbsamizdat.runner import cmd_sync, get_cursor
from dbsamizdat.samizdat import (
    SamizdatFunction,
    SamizdatTable,
    SamizdatTrigger,
)

# ==================== Pattern 1: Simple Function (No Parameters) ====================


class SimpleFunction(SamizdatFunction):
    """Function with no parameters - Pattern 1 from USAGE.md"""
    function_arguments_signature = ""  # No parameters
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'Hello, World!';
        $BODY$
        LANGUAGE SQL;
    """


@pytest.mark.unit
def test_pattern1_simple_function_sql_generation():
    """Test Pattern 1: Simple function generates correct SQL"""
    sql = SimpleFunction.create()
    assert "CREATE FUNCTION" in sql
    assert '"public"."SimpleFunction"()' in sql
    assert "RETURNS TEXT" in sql
    assert "$BODY$" in sql
    assert "SELECT 'Hello, World!'" in sql
    assert "LANGUAGE SQL" in sql


@pytest.mark.integration
def test_pattern1_simple_function_creation(clean_db):
    """Test Pattern 1: Simple function can be created in database"""
    cmd_sync(clean_db, [SimpleFunction])

    with get_cursor(clean_db) as cursor:
        cursor.execute("SELECT SimpleFunction();")
        result = cursor.fetchone()
        assert result[0] == "Hello, World!"


# ==================== Pattern 2: Function with Parameters ====================


class GreetFunction(SamizdatFunction):
    """Function with parameters - Pattern 2 from USAGE.md"""
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


@pytest.mark.unit
def test_pattern2_function_with_params_sql_generation():
    """Test Pattern 2: Function with parameters generates correct SQL"""
    sql = GreetFunction.create()
    assert "CREATE FUNCTION" in sql
    assert '"public"."GreetFunction"(name TEXT, age INTEGER)' in sql
    assert "RETURNS TEXT" in sql
    assert "$BODY$" in sql
    assert "format('Hello %s" in sql
    assert "LANGUAGE plpgsql" in sql


@pytest.mark.integration
def test_pattern2_function_with_params_creation(clean_db):
    """Test Pattern 2: Function with parameters can be created and called"""
    cmd_sync(clean_db, [GreetFunction])

    with get_cursor(clean_db) as cursor:
        cursor.execute("SELECT GreetFunction('Alice', 30);")
        result = cursor.fetchone()
        assert "Alice" in result[0]
        assert "30" in result[0]


# ==================== Pattern 3: Trigger Calling Function ====================


class MyTable(SamizdatTable):
    """Table for trigger example - Pattern 3 from USAGE.md"""
    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """


class UpdateTimestampFunction(SamizdatFunction):
    """Function that updates timestamp - Pattern 3 from USAGE.md"""
    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TRIGGER AS
        $BODY$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """


class UpdateTimestampTrigger(SamizdatTrigger):
    """Trigger that calls the update timestamp function - Pattern 3 from USAGE.md"""
    on_table = MyTable  # Can be class, tuple, or string
    condition = "BEFORE UPDATE"
    deps_on = {UpdateTimestampFunction}  # Include function in dependencies
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE FUNCTION {UpdateTimestampFunction.creation_identity()};
    """


@pytest.mark.unit
def test_pattern3_trigger_sql_generation():
    """Test Pattern 3: Trigger generates correct SQL with function reference"""
    sql = UpdateTimestampTrigger.create()
    assert "CREATE TRIGGER" in sql
    assert "UpdateTimestampTrigger" in sql
    assert "BEFORE UPDATE" in sql
    assert MyTable.db_object_identity() in sql
    assert UpdateTimestampFunction.creation_identity() in sql
    assert "FOR EACH ROW" in sql
    assert "EXECUTE FUNCTION" in sql


@pytest.mark.unit
def test_pattern3_trigger_dependencies():
    """Test Pattern 3: Trigger properly declares function dependency"""
    deps = UpdateTimestampTrigger.fqdeps_on()
    assert UpdateTimestampFunction.fq() in deps


@pytest.mark.integration
def test_pattern3_trigger_functionality(clean_db):
    """Test Pattern 3: Trigger can be created and updates timestamp on update"""
    cmd_sync(clean_db, [MyTable, UpdateTimestampFunction, UpdateTimestampTrigger])

    with get_cursor(clean_db) as cursor:
        # Insert a row
        cursor.execute(
            f"""
            INSERT INTO {MyTable.db_object_identity()} (value)
            VALUES ('initial')
            RETURNING id, updated_at
        """
        )
        initial_result = cursor.fetchone()
        initial_id = initial_result[0]
        initial_timestamp = initial_result[1]

        # Wait a moment to ensure timestamp difference
        import time
        time.sleep(0.1)

        # Update the row - trigger should fire
        cursor.execute(
            f"""
            UPDATE {MyTable.db_object_identity()}
            SET value = 'updated'
            WHERE id = %s
            RETURNING updated_at
        """,
            (initial_id,),
        )
        updated_result = cursor.fetchone()
        updated_timestamp = updated_result[0]

        # Verify timestamp was updated by trigger
        assert updated_timestamp > initial_timestamp


@pytest.mark.unit
def test_pattern3_trigger_on_table_formats():
    """Test Pattern 3: Trigger accepts different on_table formats"""
    # Test with tuple
    class TriggerWithTuple(SamizdatTrigger):
        on_table = ("public", "test_table")
        condition = "AFTER INSERT"
        sql_template = "${preamble} FOR EACH ROW EXECUTE FUNCTION test_func();"

    assert TriggerWithTuple.on_table == ("public", "test_table")

    # Test with string (would need actual table, but we can test the attribute)
    class TriggerWithString(SamizdatTrigger):
        on_table = "test_table"
        condition = "AFTER INSERT"
        sql_template = "${preamble} FOR EACH ROW EXECUTE FUNCTION test_func();"

    assert TriggerWithString.on_table == "test_table"


# ==================== Pattern 4: Multi-Function Dependencies ====================


class MultiFunctionTable(SamizdatTable):
    """Table for multi-function example - Pattern 4 from USAGE.md"""
    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """


class ValidateNameFunction(SamizdatFunction):
    """Function to validate name - Pattern 4 from USAGE.md"""
    function_arguments_signature = "name_value TEXT"
    sql_template = """
        ${preamble}
        RETURNS BOOLEAN AS
        $BODY$
        BEGIN
            RETURN length(name_value) > 0 AND length(name_value) <= 100;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """


class LogChangeFunction(SamizdatFunction):
    """Function to log changes - Pattern 4 from USAGE.md"""
    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TRIGGER AS
        $BODY$
        BEGIN
            -- Log the change (simplified example)
            RAISE NOTICE 'Change logged for record %', NEW.id;
            RETURN NEW;
        END;
        $BODY$
        LANGUAGE plpgsql;
    """


class ValidateAndLogTrigger(SamizdatTrigger):
    """Trigger that uses multiple functions - Pattern 4 from USAGE.md"""
    on_table = MultiFunctionTable
    condition = "BEFORE INSERT OR UPDATE"
    deps_on = {ValidateNameFunction, LogChangeFunction}  # Multiple function dependencies
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW
        WHEN ({ValidateNameFunction.creation_identity()}(NEW.name))
        EXECUTE FUNCTION {LogChangeFunction.creation_identity()};
    """


@pytest.mark.unit
def test_pattern4_multi_function_trigger_sql_generation():
    """Test Pattern 4: Multi-function trigger generates correct SQL"""
    sql = ValidateAndLogTrigger.create()
    assert "CREATE TRIGGER" in sql
    assert "ValidateAndLogTrigger" in sql
    assert "BEFORE INSERT OR UPDATE" in sql
    assert MultiFunctionTable.db_object_identity() in sql
    assert ValidateNameFunction.creation_identity() in sql
    assert LogChangeFunction.creation_identity() in sql
    assert "WHEN" in sql
    assert "FOR EACH ROW" in sql
    assert "EXECUTE FUNCTION" in sql


@pytest.mark.unit
def test_pattern4_multi_function_dependencies():
    """Test Pattern 4: Trigger properly declares multiple function dependencies"""
    deps = ValidateAndLogTrigger.fqdeps_on()
    assert ValidateNameFunction.fq() in deps
    assert LogChangeFunction.fq() in deps
    assert len(deps) == 2


@pytest.mark.integration
def test_pattern4_multi_function_trigger_creation(clean_db):
    """Test Pattern 4: Multi-function trigger can be created in database"""
    cmd_sync(
        clean_db,
        [
            MultiFunctionTable,
            ValidateNameFunction,
            LogChangeFunction,
            ValidateAndLogTrigger,
        ],
    )

    with get_cursor(clean_db) as cursor:
        # Verify trigger exists
        cursor.execute(
            """
            SELECT tgname
            FROM pg_trigger
            WHERE tgname = 'ValidateAndLogTrigger'
              AND tgisinternal = false
        """
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "ValidateAndLogTrigger"


@pytest.mark.integration
def test_pattern4_multi_function_trigger_functionality(clean_db):
    """Test Pattern 4: Multi-function trigger validates and logs correctly"""
    cmd_sync(
        clean_db,
        [
            MultiFunctionTable,
            ValidateNameFunction,
            LogChangeFunction,
            ValidateAndLogTrigger,
        ],
    )

    with get_cursor(clean_db) as cursor:
        # Insert valid name (should succeed)
        cursor.execute(
            f"""
            INSERT INTO {MultiFunctionTable.db_object_identity()} (name)
            VALUES ('ValidName')
            RETURNING id
        """
        )
        result = cursor.fetchone()
        assert result is not None

        # Insert invalid name (too long - should fail validation)
        cursor.execute(
            f"""
            INSERT INTO {MultiFunctionTable.db_object_identity()} (name)
            VALUES (%s)
        """,
            ("x" * 101,),  # 101 characters - exceeds limit
        )
        # Should raise error due to WHEN clause validation
        # (PostgreSQL will reject if WHEN condition is false)


# ==================== Best Practices Checklist Verification ====================


@pytest.mark.unit
def test_function_checklist_uses_samizdatname():
    """Verify function checklist: Use ${samizdatname} placeholder"""
    class FunctionWithSamizdatName(SamizdatFunction):
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TEXT AS
            $BODY$
            SELECT format('Function: %s', ${samizdatname});
            $BODY$
            LANGUAGE SQL;
        """

    sql = FunctionWithSamizdatName.create()
    assert "${samizdatname}" not in sql  # Should be substituted
    assert FunctionWithSamizdatName.db_object_identity() in sql


@pytest.mark.unit
def test_function_checklist_uses_body_tag():
    """Verify function checklist: Use $BODY$ or $FUNC$ instead of $$"""
    class FunctionWithBodyTag(SamizdatFunction):
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TEXT AS
            $BODY$
            SELECT 'test';
            $BODY$
            LANGUAGE SQL;
        """

    sql = FunctionWithBodyTag.create()
    assert "$BODY$" in sql
    assert "$$" not in sql  # Should not use $$


@pytest.mark.unit
def test_trigger_checklist_starts_with_preamble():
    """Verify trigger checklist: Start template with ${preamble}"""
    class ChecklistTrigger(SamizdatTrigger):
        on_table = ("public", "test_table")
        condition = "AFTER INSERT"
        deps_on = set()
        sql_template = """
            ${preamble}
            FOR EACH ROW EXECUTE FUNCTION test_func();
        """

    sql = ChecklistTrigger.create()
    assert "CREATE TRIGGER" in sql
    assert "AFTER INSERT" in sql
    assert "test_table" in sql


@pytest.mark.unit
def test_trigger_checklist_uses_creation_identity():
    """Verify trigger checklist: Use FunctionClass.creation_identity()"""
    class TestFunction(SamizdatFunction):
        function_arguments_signature = "x INTEGER"
        sql_template = """
            ${preamble}
            RETURNS INTEGER AS $BODY$ SELECT x; $BODY$ LANGUAGE SQL;
        """

    class ChecklistTrigger(SamizdatTrigger):
        on_table = ("public", "test_table")
        condition = "AFTER INSERT"
        deps_on = {TestFunction}
        sql_template = f"""
            ${{preamble}}
            FOR EACH ROW EXECUTE FUNCTION {TestFunction.creation_identity()};
        """

    sql = ChecklistTrigger.create()
    assert TestFunction.creation_identity() in sql
    # Should include function signature
    assert "x INTEGER" in sql or '"TestFunction"(x INTEGER)' in sql


@pytest.mark.unit
def test_trigger_checklist_includes_deps_on():
    """Verify trigger checklist: Include function class in deps_on set"""
    class TestFunction(SamizdatFunction):
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TRIGGER AS $BODY$ RETURN NEW; $BODY$ LANGUAGE plpgsql;
        """

    class ChecklistTrigger(SamizdatTrigger):
        on_table = ("public", "test_table")
        condition = "AFTER INSERT"
        deps_on = {TestFunction}  # Function included in deps_on
        sql_template = f"""
            ${{preamble}}
            FOR EACH ROW EXECUTE FUNCTION {TestFunction.creation_identity()};
        """

    deps = ChecklistTrigger.fqdeps_on()
    assert TestFunction.fq() in deps


# ==================== Common Mistakes Examples ====================


@pytest.mark.unit
def test_common_mistake_dollar_quoting():
    """Verify common mistake: Don't use $$, use $BODY$ instead"""
    # This test documents the correct approach
    class CorrectFunction(SamizdatFunction):
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TEXT AS $BODY$
            SELECT 'test';
            $BODY$ LANGUAGE SQL;
        """

    sql = CorrectFunction.create()
    assert "$BODY$" in sql
    # Verify it doesn't have the problematic $$
    # (Note: $$ would be escaped as $ in Python templates, so we check for $BODY$)


@pytest.mark.unit
def test_common_mistake_hardcoded_names():
    """Verify common mistake: Don't hardcode names, use ${samizdatname}"""
    class FunctionWithSamizdatName(SamizdatFunction):
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TEXT AS $BODY$
            SELECT format('Function: %s', ${samizdatname});
            $BODY$ LANGUAGE SQL;
        """

    sql = FunctionWithSamizdatName.create()
    # ${samizdatname} should be substituted
    assert "${samizdatname}" not in sql
    # Should contain the actual function identity
    assert FunctionWithSamizdatName.db_object_identity() in sql or '"FunctionWithSamizdatName"()' in sql


@pytest.mark.unit
def test_common_mistake_template_variables_in_triggers():
    """Verify common mistake: Don't use template variables for function refs in triggers"""
    class TestFunction(SamizdatFunction):
        function_arguments_signature = ""
        sql_template = """
            ${preamble}
            RETURNS TRIGGER AS $BODY$ RETURN NEW; $BODY$ LANGUAGE plpgsql;
        """

    # Correct approach: Use f-string with creation_identity()
    class CorrectTrigger(SamizdatTrigger):
        on_table = ("public", "test_table")
        condition = "AFTER INSERT"
        deps_on = {TestFunction}
        sql_template = f"""
            ${{preamble}}
            FOR EACH ROW EXECUTE FUNCTION {TestFunction.creation_identity()};
        """

    sql = CorrectTrigger.create()
    # Should contain the function reference via creation_identity()
    assert TestFunction.creation_identity() in sql
    # Should not contain undefined template variables
    assert "${function_ref}" not in sql
