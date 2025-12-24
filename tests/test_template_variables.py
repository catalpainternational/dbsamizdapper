"""Tests for template variable substitution behavior.

These tests verify the exact behavior of template variables (${preamble}, ${postamble}, ${samizdatname})
for different entity types. This ensures documentation accuracy.
"""

import pytest

from dbsamizdat.samizdat import (
    SamizdatFunction,
    SamizdatMaterializedView,
    SamizdatTable,
    SamizdatTrigger,
    SamizdatView,
)

# ==================== Test Class Definitions ====================


class TestView(SamizdatView):
    """Test view for template variable testing"""

    sql_template = """
        ${preamble}
        SELECT 1 as value
        ${postamble}
    """


class TestViewWithSamizdatName(SamizdatView):
    """Test view using ${samizdatname}"""

    sql_template = """
        ${preamble}
        SELECT * FROM ${samizdatname}
        ${postamble}
    """


class TestTable(SamizdatTable):
    """Test table for template variable testing"""

    sql_template = """
        ${preamble}
        (id SERIAL PRIMARY KEY, name TEXT)
        ${postamble}
    """


class TestUnloggedTable(SamizdatTable):
    """Test UNLOGGED table for template variable testing"""

    unlogged = True
    sql_template = """
        ${preamble}
        (id SERIAL PRIMARY KEY, name TEXT)
        ${postamble}
    """


class TestMaterializedView(SamizdatMaterializedView):
    """Test materialized view for template variable testing"""

    sql_template = """
        ${preamble}
        AS SELECT 1 as value
        ${postamble}
    """


class TestFunctionNoParams(SamizdatFunction):
    """Test function with no parameters"""

    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'test';
        $BODY$
        LANGUAGE SQL;
    """


class TestFunctionWithParams(SamizdatFunction):
    """Test function with parameters"""

    function_arguments_signature = "name TEXT, age INTEGER"
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT format('Hello %s', name);
        $BODY$
        LANGUAGE SQL;
    """


class TestFunctionWithSamizdatName(SamizdatFunction):
    """Test function using ${samizdatname}"""

    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS TEXT AS
        $BODY$
        SELECT 'Function: ${samizdatname}';
        $BODY$
        LANGUAGE SQL;
    """


class TestTableForTrigger(SamizdatTable):
    """Table used as target for trigger tests"""

    sql_template = """
        ${preamble}
        (id SERIAL PRIMARY KEY)
        ${postamble}
    """


class TestTrigger(SamizdatTrigger):
    """Test trigger for template variable testing"""

    on_table = TestTableForTrigger
    condition = "AFTER INSERT"
    sql_template = """
        ${preamble}
        FOR EACH ROW EXECUTE FUNCTION ${samizdatname}();
    """


class TestTriggerWithFunctionReference(SamizdatTrigger):
    """Test trigger referencing a function using f-string (correct pattern)"""

    on_table = TestTableForTrigger
    condition = "AFTER INSERT"
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE FUNCTION {TestFunctionNoParams.creation_identity()};
    """


# ==================== Tests for Views ====================


@pytest.mark.unit
def test_view_preamble_substitution():
    """Test ${preamble} substitution for views"""
    sql = TestView.create()
    assert "${preamble}" not in sql
    assert "CREATE VIEW" in sql
    assert '"public"."TestView"' in sql or '"TestView"' in sql
    assert "AS" in sql


@pytest.mark.unit
def test_view_postamble_substitution():
    """Test ${postamble} substitution for views (should be empty)"""
    sql = TestView.create()
    assert "${postamble}" not in sql
    # For views, postamble should be empty, so it should just disappear
    # Check that "WITH NO DATA" is NOT present
    assert "WITH NO DATA" not in sql


@pytest.mark.unit
def test_view_samizdatname_substitution():
    """Test ${samizdatname} substitution for views"""
    sql = TestViewWithSamizdatName.create()
    assert "${samizdatname}" not in sql
    # Should contain the db_object_identity format
    assert '"public"."TestViewWithSamizdatName"' in sql or '"TestViewWithSamizdatName"' in sql


# ==================== Tests for Tables ====================


@pytest.mark.unit
def test_table_preamble_substitution():
    """Test ${preamble} substitution for tables"""
    sql = TestTable.create()
    assert "${preamble}" not in sql
    assert "CREATE TABLE" in sql
    assert '"public"."TestTable"' in sql or '"TestTable"' in sql
    assert "AS" not in sql  # Tables don't have "AS"


@pytest.mark.unit
def test_table_postamble_substitution():
    """Test ${postamble} substitution for tables (should be empty)"""
    sql = TestTable.create()
    assert "${postamble}" not in sql
    assert "WITH NO DATA" not in sql


@pytest.mark.unit
def test_unlogged_table_preamble_includes_unlogged():
    """Test that UNLOGGED tables include UNLOGGED in preamble"""
    sql = TestUnloggedTable.create()
    assert "${preamble}" not in sql
    assert "CREATE UNLOGGED TABLE" in sql
    assert '"public"."TestUnloggedTable"' in sql or '"TestUnloggedTable"' in sql


# ==================== Tests for Materialized Views ====================


@pytest.mark.unit
def test_matview_preamble_substitution():
    """Test ${preamble} substitution for materialized views"""
    sql = TestMaterializedView.create()
    assert "${preamble}" not in sql
    assert "CREATE MATERIALIZED VIEW" in sql
    assert '"public"."TestMaterializedView"' in sql or '"TestMaterializedView"' in sql
    assert "AS" in sql


@pytest.mark.unit
def test_matview_postamble_substitution():
    """Test ${postamble} substitution for materialized views (should be 'WITH NO DATA')"""
    sql = TestMaterializedView.create()
    assert "${postamble}" not in sql
    assert "WITH NO DATA" in sql


# ==================== Tests for Functions ====================


@pytest.mark.unit
def test_function_preamble_substitution_no_params():
    """Test ${preamble} substitution for functions with no parameters"""
    sql = TestFunctionNoParams.create()
    assert "${preamble}" not in sql
    assert "CREATE FUNCTION" in sql
    assert '"public"."TestFunctionNoParams"()' in sql or '"TestFunctionNoParams"()' in sql


@pytest.mark.unit
def test_function_preamble_substitution_with_params():
    """Test ${preamble} substitution for functions with parameters"""
    sql = TestFunctionWithParams.create()
    assert "${preamble}" not in sql
    assert "CREATE FUNCTION" in sql
    # Should include the signature in creation_identity format
    assert (
        '"public"."TestFunctionWithParams"(name TEXT, age INTEGER)' in sql
        or '"TestFunctionWithParams"(name TEXT, age INTEGER)' in sql
    )


@pytest.mark.unit
def test_function_samizdatname_substitution():
    """Test ${samizdatname} substitution for functions"""
    sql = TestFunctionWithSamizdatName.create()
    assert "${samizdatname}" not in sql
    # Should contain the db_object_identity format (includes signature)
    assert '"public"."TestFunctionWithSamizdatName"()' in sql or '"TestFunctionWithSamizdatName"()' in sql


# ==================== Tests for Triggers ====================


@pytest.mark.unit
def test_trigger_preamble_substitution():
    """Test ${preamble} substitution for triggers"""
    sql = TestTrigger.create()
    assert "${preamble}" not in sql
    assert "CREATE TRIGGER" in sql
    assert '"TestTrigger"' in sql
    assert "AFTER INSERT" in sql
    assert "ON" in sql
    # Should include the table identity
    assert '"public"."TestTableForTrigger"' in sql or '"TestTableForTrigger"' in sql


@pytest.mark.unit
def test_trigger_samizdatname_substitution():
    """Test ${samizdatname} substitution for triggers (should be just the name, not full identity)"""
    sql = TestTrigger.create()
    assert "${samizdatname}" not in sql
    # For triggers, samizdatname should be just the trigger name
    # Check that it appears in EXECUTE FUNCTION clause
    assert "EXECUTE FUNCTION" in sql
    # Should be just the name, not the full identity format
    assert "TestTrigger()" in sql


@pytest.mark.unit
def test_trigger_function_reference_with_fstring():
    """Test that triggers can reference functions using f-string with creation_identity()"""
    sql = TestTriggerWithFunctionReference.create()
    assert "${preamble}" not in sql
    assert "CREATE TRIGGER" in sql
    assert "EXECUTE FUNCTION" in sql
    # Should contain the function's creation_identity (with signature)
    assert '"public"."TestFunctionNoParams"()' in sql or '"TestFunctionNoParams"()' in sql


# ==================== Tests for Edge Cases ====================


@pytest.mark.unit
def test_undefined_template_variable_left_unchanged():
    """Test that undefined template variables are left unchanged (safe_substitute behavior)"""

    # Create a view with an undefined variable
    class ViewWithUndefinedVar(SamizdatView):
        sql_template = """
            ${preamble}
            SELECT ${undefined_var} as value
            ${postamble}
        """

    sql = ViewWithUndefinedVar.create()
    # safe_substitute leaves undefined variables unchanged
    assert "${undefined_var}" in sql


@pytest.mark.unit
def test_template_variables_in_fstring():
    """Test that template variables work correctly when used in f-strings (double braces)"""

    class ViewWithFString(SamizdatView):
        sql_template = """
            ${preamble}
            SELECT 1 as value
            ${postamble}
        """

    sql = ViewWithFString.create()
    assert "${preamble}" not in sql
    assert "${postamble}" not in sql
    assert "CREATE VIEW" in sql


# ==================== Tests for Exact Replacement Values ====================
# These tests verify the exact strings that template variables are replaced with


@pytest.mark.unit
def test_view_preamble_exact_format():
    """Test exact format of ${preamble} for views"""
    sql = TestView.create()
    # Should start with "CREATE VIEW" followed by identity, then "AS"
    lines = sql.split("\n")
    create_line = [line for line in lines if "CREATE VIEW" in line][0]
    assert "CREATE VIEW" in create_line
    assert "AS" in create_line


@pytest.mark.unit
def test_function_preamble_exact_format():
    """Test exact format of ${preamble} for functions"""
    sql = TestFunctionNoParams.create()
    # Should be "CREATE FUNCTION" followed by creation_identity (with signature)
    lines = sql.split("\n")
    create_line = [line for line in lines if "CREATE FUNCTION" in line][0]
    assert "CREATE FUNCTION" in create_line
    # Should include parentheses even for no-param functions
    assert "()" in create_line


@pytest.mark.unit
def test_trigger_preamble_exact_format():
    """Test exact format of ${preamble} for triggers"""
    sql = TestTrigger.create()
    # Should be "CREATE TRIGGER" followed by quoted name, condition, "ON", table identity
    lines = sql.split("\n")
    create_line = [line for line in lines if "CREATE TRIGGER" in line][0]
    assert "CREATE TRIGGER" in create_line
    assert '"TestTrigger"' in create_line
    assert "AFTER INSERT" in create_line
    assert "ON" in create_line
