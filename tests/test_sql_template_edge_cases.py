"""Tests for sql_template and definition_hash edge cases

Tests cover:
- String templates
- Callable templates
- Reconstructed classes (no sql_template)
- Edge cases with implanted_hash (None, empty string, "None")
- Missing sql_template attribute
"""

import pytest

from dbsamizdat.libdb import StateTuple, dbinfo_to_class
from dbsamizdat.samizdat import SamizdatView

# ==================== Test Class Definitions ====================


class ViewWithStringTemplate(SamizdatView):
    """View with string sql_template"""

    sql_template = """
        ${preamble}
        SELECT 1 as value
        ${postamble}
    """


class ViewWithCallableTemplate(SamizdatView):
    """View with callable sql_template (simulating SamizdatQuerySet pattern)"""

    _template_value = "SELECT 2 as value"

    @classmethod
    def sql_template(cls):
        return f"""
            ${{preamble}}
            {cls._template_value}
            ${{postamble}}
        """


# ==================== Tests for get_sql_template ====================


@pytest.mark.unit
def test_get_sql_template_with_string():
    """Test get_sql_template with string template"""
    template = ViewWithStringTemplate.get_sql_template()
    assert isinstance(template, str)
    assert "SELECT 1" in template


@pytest.mark.unit
def test_get_sql_template_with_callable():
    """Test get_sql_template with callable template"""
    template = ViewWithCallableTemplate.get_sql_template()
    assert isinstance(template, str)
    assert "SELECT 2" in template


@pytest.mark.unit
def test_get_sql_template_missing_attribute():
    """Test get_sql_template raises AttributeError when sql_template is missing"""

    # Create a class without sql_template
    class IncompleteView(SamizdatView):
        pass  # No sql_template defined

    with pytest.raises(AttributeError, match="has no 'sql_template' attribute"):
        IncompleteView.get_sql_template()


@pytest.mark.unit
def test_get_sql_template_reconstructed_class():
    """Test get_sql_template on reconstructed class (from database)"""
    # Create a reconstructed class (simulating dbinfo_to_class output)
    info = StateTuple(
        schemaname="public",
        viewname="reconstructed_view",
        objecttype="VIEW",
        commentcontent='{"dbsamizdat": {"version": 1, "definition_hash": "abc123"}}',
        args=None,
        definition_hash="abc123",
    )

    reconstructed = dbinfo_to_class(info)

    # Reconstructed classes don't have sql_template
    with pytest.raises(AttributeError, match="dynamically reconstructed class"):
        reconstructed.get_sql_template()


# ==================== Tests for definition_hash ====================


@pytest.mark.unit
def test_definition_hash_with_implanted_hash():
    """Test definition_hash returns implanted_hash when set"""
    info = StateTuple(
        schemaname="public",
        viewname="test_view",
        objecttype="VIEW",
        commentcontent='{"dbsamizdat": {"version": 1, "definition_hash": "implanted_hash_value"}}',
        args=None,
        definition_hash="implanted_hash_value",
    )

    reconstructed = dbinfo_to_class(info)
    assert reconstructed.definition_hash() == "implanted_hash_value"


@pytest.mark.unit
def test_definition_hash_with_empty_string():
    """Test definition_hash computes hash when implanted_hash is empty string"""
    info = StateTuple(
        schemaname="public",
        viewname="test_view",
        objecttype="VIEW",
        commentcontent='{"dbsamizdat": {"version": 1, "definition_hash": ""}}',
        args=None,
        definition_hash="",  # Empty string
    )

    reconstructed = dbinfo_to_class(info)
    # Should try to compute hash, which will fail because no sql_template
    # But the check should handle empty string correctly
    with pytest.raises(AttributeError, match="dynamically reconstructed class"):
        reconstructed.definition_hash()


@pytest.mark.unit
def test_definition_hash_with_none_string():
    """Test definition_hash computes hash when implanted_hash is string 'None'"""
    info = StateTuple(
        schemaname="public",
        viewname="test_view",
        objecttype="VIEW",
        commentcontent='{"dbsamizdat": {"version": 1}}',
        args=None,
        definition_hash=None,  # Will become "None" string
    )

    reconstructed = dbinfo_to_class(info)
    # str(None) becomes "None", which should be treated as invalid
    with pytest.raises(AttributeError, match="dynamically reconstructed class"):
        reconstructed.definition_hash()


@pytest.mark.unit
def test_definition_hash_computes_for_regular_class():
    """Test definition_hash computes hash for regular class without implanted_hash"""
    # Regular class without implanted_hash should compute hash
    hash1 = ViewWithStringTemplate.definition_hash()
    assert isinstance(hash1, str)
    assert len(hash1) == 32  # MD5 hash length

    # Should be consistent
    hash2 = ViewWithStringTemplate.definition_hash()
    assert hash1 == hash2


@pytest.mark.unit
def test_definition_hash_uses_implanted_hash_when_set():
    """Test definition_hash uses implanted_hash when set on regular class"""
    # Set implanted_hash on a regular class
    ViewWithStringTemplate.implanted_hash = "custom_hash_value"
    try:
        assert ViewWithStringTemplate.definition_hash() == "custom_hash_value"
    finally:
        # Clean up
        ViewWithStringTemplate.implanted_hash = None


@pytest.mark.unit
def test_definition_hash_ignores_empty_implanted_hash():
    """Test definition_hash computes hash when implanted_hash is empty string"""
    ViewWithStringTemplate.implanted_hash = ""
    try:
        # Should compute hash, not use empty string
        hash_value = ViewWithStringTemplate.definition_hash()
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32
        assert hash_value != ""
    finally:
        ViewWithStringTemplate.implanted_hash = None


@pytest.mark.unit
def test_definition_hash_ignores_none_string_implanted_hash():
    """Test definition_hash computes hash when implanted_hash is string 'None'"""
    ViewWithStringTemplate.implanted_hash = "None"
    try:
        # Should compute hash, not use "None" string
        hash_value = ViewWithStringTemplate.definition_hash()
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32
        assert hash_value != "None"
    finally:
        ViewWithStringTemplate.implanted_hash = None


@pytest.mark.unit
def test_definition_hash_with_callable_template():
    """Test definition_hash works with callable sql_template"""
    hash_value = ViewWithCallableTemplate.definition_hash()
    assert isinstance(hash_value, str)
    assert len(hash_value) == 32


# ==================== Integration Tests ====================


@pytest.mark.unit
def test_head_id_uses_definition_hash():
    """Test that head_id() uses definition_hash correctly"""
    # Regular class
    head1 = ViewWithStringTemplate.head_id()
    assert isinstance(head1, int)

    # Should be consistent
    head2 = ViewWithStringTemplate.head_id()
    assert head1 == head2

    # Reconstructed class
    info = StateTuple(
        schemaname="public",
        viewname="test_view",
        objecttype="VIEW",
        commentcontent='{"dbsamizdat": {"version": 1, "definition_hash": "test_hash"}}',
        args=None,
        definition_hash="test_hash",
    )
    reconstructed = dbinfo_to_class(info)
    head3 = reconstructed.head_id()
    assert isinstance(head3, int)
    # Should be different from regular class
    assert head3 != head1


@pytest.mark.unit
def test_reconstructed_class_head_id_with_empty_hash():
    """Test head_id on reconstructed class with empty definition_hash"""
    info = StateTuple(
        schemaname="public",
        viewname="test_view",
        objecttype="VIEW",
        commentcontent='{"dbsamizdat": {"version": 1, "definition_hash": ""}}',
        args=None,
        definition_hash="",  # Empty string
    )

    reconstructed = dbinfo_to_class(info)
    # head_id() calls definition_hash(), which will try to compute hash
    # This should raise AttributeError because no sql_template
    with pytest.raises(AttributeError, match="dynamically reconstructed class"):
        reconstructed.head_id()
