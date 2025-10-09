"""Tests for the samizdat loader module"""

from importlib import import_module

import pytest

from dbsamizdat.loader import samizdats_in_app, samizdats_in_module
from dbsamizdat.samtypes import entitypes
from sample_app.dbsamizdat_defs import AView, ExampleTable, ViewOnTable


@pytest.mark.unit
def test_load_from_module():
    """Test loading samizdats from a module"""
    m = import_module("sample_app.test_samizdats")
    samizdats = list(samizdats_in_module(m))

    # Verify we found samizdats
    assert len(samizdats) > 0, "Should find samizdats in module"

    # Verify they're valid samizdat classes
    assert all(hasattr(s, "entity_type") for s in samizdats)
    assert all(hasattr(s, "sql_template") for s in samizdats)
    assert all(hasattr(s, "fq") for s in samizdats)


@pytest.mark.unit
def test_import_from_app():
    """Test loading samizdats from an app"""
    samizdats = set(samizdats_in_app("sample_app"))

    # Verify expected samizdats are found
    assert samizdats == {AView, ExampleTable, ViewOnTable}

    # Verify they have correct entity types
    assert AView.entity_type == entitypes.VIEW
    assert ExampleTable.entity_type == entitypes.TABLE
    assert ViewOnTable.entity_type == entitypes.VIEW


@pytest.mark.django
def test_autodiscover(django_setup):
    """
    Test autodiscover functionality.

    Requires Django to be configured.
    """
    from dbsamizdat.loader import autodiscover_samizdats

    # With Django configured, should return a list
    result = list(autodiscover_samizdats())
    assert isinstance(result, list)


@pytest.mark.unit
@pytest.mark.parametrize(
    "module_name",
    [
        "sample_app.test_samizdats",
        "sample_app.dbsamizdat_defs",
    ],
)
def test_load_from_multiple_modules(module_name):
    """Test loading from different modules"""
    m = import_module(module_name)
    samizdats = list(samizdats_in_module(m))

    # Should not raise
    assert isinstance(samizdats, list)
    # Each should be a valid samizdat class
    for sd in samizdats:
        assert hasattr(sd, "entity_type")
        assert hasattr(sd, "create")
        assert hasattr(sd, "drop")
