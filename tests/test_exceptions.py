"""Tests for exception classes in dbsamizdat.exceptions"""

import pytest

from dbsamizdat import SamizdatFunction, SamizdatView
from dbsamizdat.exceptions import DatabaseError, FunctionSignatureError, SamizdatException, sqlfmt


@pytest.mark.unit
def test_sqlfmt_function():
    """Test sqlfmt() formats SQL with indentation"""
    sql = "SELECT 1\nFROM users\nWHERE id = 1"
    formatted = sqlfmt(sql)

    # Should add indentation to each line
    assert "\t\t" in formatted
    assert "SELECT 1" in formatted
    assert "FROM users" in formatted


@pytest.mark.unit
def test_sqlfmt_multiline_sql():
    """Test sqlfmt() handles multiline SQL correctly"""
    sql = """CREATE VIEW test AS
SELECT id, name
FROM users
WHERE active = true"""
    formatted = sqlfmt(sql)

    lines = formatted.split("\n")
    # All lines should be indented
    assert all(line.startswith("\t\t") or line == "" for line in lines if line.strip())


@pytest.mark.unit
def test_database_error_formatting():
    """Test DatabaseError formats error message correctly"""

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    error = Exception("SQL syntax error")
    db_error = DatabaseError("create failed", error, TestView, "CREATE VIEW test AS SELECT 1")

    error_str = str(db_error)
    assert "create failed" in error_str
    assert "TestView" in error_str or "test" in error_str.lower()


@pytest.mark.unit
def test_database_error_with_none_samizdat():
    """Test DatabaseError handles None samizdat gracefully"""
    error = Exception("SQL syntax error")
    db_error = DatabaseError("create failed", error, None, "CREATE VIEW test AS SELECT 1")

    error_str = str(db_error)
    assert "create failed" in error_str
    # Should not crash with None samizdat


@pytest.mark.unit
def test_function_signature_error():
    """Test FunctionSignatureError shows candidate signatures"""

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"
        function_arguments_signature = "name text"  # Required attribute
        function_arguments = "name text"  # Also required for error message

    error = FunctionSignatureError(TestFunc, ["text", "integer"])
    error_str = str(error)

    assert "TestFunc" in error_str or "function" in error_str.lower()
    # Should mention candidate signatures or the function
    assert "candidate" in error_str.lower() or "signature" in error_str.lower() or "text" in error_str


@pytest.mark.unit
def test_function_signature_error_empty_candidates():
    """Test FunctionSignatureError handles empty candidate list"""

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"
        function_arguments_signature = "name text"  # Required attribute
        function_arguments = "name text"  # Also required for error message

    error = FunctionSignatureError(TestFunc, [])
    error_str = str(error)

    assert "TestFunc" in error_str or "function" in error_str.lower()
    # Should not crash with empty candidates


@pytest.mark.unit
def test_samizdat_exception_base_class():
    """Test that SamizdatException is a proper exception"""
    exception = SamizdatException("Test message")
    assert isinstance(exception, Exception)
    assert str(exception) == "Test message"


@pytest.mark.unit
def test_database_error_inheritance():
    """Test that DatabaseError inherits from SamizdatException"""

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    error = Exception("SQL error")
    db_error = DatabaseError("create failed", error, TestView, "CREATE VIEW...")

    assert isinstance(db_error, SamizdatException)
    assert isinstance(db_error, Exception)


@pytest.mark.unit
def test_function_signature_error_inheritance():
    """Test that FunctionSignatureError inherits from SamizdatException"""

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"

    error = FunctionSignatureError(TestFunc, ["text"])

    assert isinstance(error, SamizdatException)
    assert isinstance(error, Exception)


@pytest.mark.unit
def test_database_error_with_template_context():
    """Test DatabaseError includes template context when provided"""

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    error = Exception("SQL syntax error")
    template = TestView.get_sql_template()
    substitutions = {"preamble": "CREATE VIEW test AS", "postamble": "", "samizdatname": '"public"."test"'}
    db_error = DatabaseError("create failed", error, TestView, "CREATE VIEW test AS SELECT 1", template, substitutions)

    error_str = str(db_error)
    assert "Original template" in error_str
    assert "Template variable substitutions" in error_str
    assert "CREATE VIEW test AS" in error_str or "preamble" in error_str


@pytest.mark.unit
def test_database_error_with_function_signature():
    """Test DatabaseError includes function_arguments_signature for functions"""

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"
        function_arguments_signature = "name text"

    error = Exception("SQL syntax error")
    db_error = DatabaseError("create failed", error, TestFunc, "CREATE FUNCTION...", None, None)

    error_str = str(db_error)
    assert "function_arguments_signature" in error_str
    assert "name text" in error_str


@pytest.mark.unit
def test_database_error_detects_signature_duplication():
    """Test error pattern detection for signature duplication"""

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"
        function_arguments_signature = "name text"

    error = Exception('syntax error at or near "("')
    sql = "CREATE FUNCTION test()(name text) RETURNS TEXT..."
    db_error = DatabaseError("create failed", error, TestFunc, sql, None, None)

    error_str = str(db_error)
    assert "Signature duplication" in error_str or "Hint" in error_str


@pytest.mark.unit
def test_database_error_detects_missing_create_function():
    """Test error pattern detection for missing CREATE FUNCTION"""

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"
        function_arguments_signature = "name text"

    error = Exception('syntax error at or near "RETURNS"')
    sql = "RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"
    db_error = DatabaseError("create failed", error, TestFunc, sql, None, None)

    error_str = str(db_error)
    assert "Missing CREATE FUNCTION" in error_str or "Hint" in error_str


@pytest.mark.unit
def test_database_error_detects_invalid_template_variable():
    """Test error pattern detection for invalid template variables"""

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    error = Exception('syntax error at or near "$"')
    sql = "CREATE VIEW test AS SELECT $invalid"
    db_error = DatabaseError("create failed", error, TestView, sql, None, None)

    error_str = str(db_error)
    assert "Invalid template variable" in error_str or "Hint" in error_str


@pytest.mark.unit
def test_database_error_without_template_context():
    """Test DatabaseError works without template context (backward compatibility)"""

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    error = Exception("SQL syntax error")
    db_error = DatabaseError("create failed", error, TestView, "CREATE VIEW test AS SELECT 1", None, None)

    error_str = str(db_error)
    assert "create failed" in error_str
    assert "CREATE VIEW test AS SELECT 1" in error_str
    # Should not crash without template context
