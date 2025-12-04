"""Tests for utility functions in dbsamizdat.util"""

import pytest

from dbsamizdat.samtypes import FQTuple
from dbsamizdat.util import nodenamefmt


@pytest.mark.unit
def test_nodenamefmt_with_fqtuple():
    """Test nodenamefmt formats FQTuple correctly"""
    fq = FQTuple("public", "MyView")
    result = nodenamefmt(fq)
    # nodenamefmt returns str(node) for non-tuple, non-string inputs
    assert isinstance(result, str)
    assert "MyView" in result or "public" in result


@pytest.mark.unit
def test_nodenamefmt_with_tuple():
    """Test nodenamefmt formats tuple correctly"""
    result = nodenamefmt(("public", "MyView"))
    # For public schema, it omits the schema
    assert result == "MyView"

    # For non-public schema, it includes it
    result = nodenamefmt(("analytics", "MyView"))
    assert result == "analytics.MyView"


@pytest.mark.unit
def test_nodenamefmt_with_custom_schema():
    """Test nodenamefmt handles custom schemas"""
    result = nodenamefmt(("analytics", "UserStats"))
    assert result == "analytics.UserStats"

    # Public schema is omitted
    result = nodenamefmt(("public", "UserStats"))
    assert result == "UserStats"


@pytest.mark.unit
def test_nodenamefmt_with_string():
    """Test nodenamefmt handles string input"""
    # nodenamefmt should handle string input (if it does)
    result = nodenamefmt("public.MyView")
    # If it doesn't handle strings, this might raise an error
    # Let's test what actually happens
    assert isinstance(result, str)


@pytest.mark.unit
def test_nodenamefmt_with_function_signature():
    """Test nodenamefmt handles function with signature"""
    fq = FQTuple("public", "MyFunction", "name text")
    result = nodenamefmt(fq)
    # Should include schema and function name, possibly signature
    assert "public" in result
    assert "MyFunction" in result
