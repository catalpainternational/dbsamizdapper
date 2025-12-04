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


@pytest.mark.django
def test_autodiscover_includes_dbsamizdat_modules(django_setup):
    """
    Test that autodiscover includes modules from DBSAMIZDAT_MODULES setting.

    Requires Django to be configured.
    """
    from django.conf import settings

    from dbsamizdat.loader import autodiscover_samizdats

    # Get baseline - samizdats from installed apps
    original_modules = getattr(settings, "DBSAMIZDAT_MODULES", [])
    try:
        # Clear DBSAMIZDAT_MODULES to get baseline
        if hasattr(settings, "DBSAMIZDAT_MODULES"):
            delattr(settings, "DBSAMIZDAT_MODULES")
        baseline = set(autodiscover_samizdats())

        # Add DBSAMIZDAT_MODULES setting
        settings.DBSAMIZDAT_MODULES = ["sample_app.test_samizdats"]
        with_modules = set(autodiscover_samizdats())

        # Should have more samizdats when DBSAMIZDAT_MODULES is set
        assert len(with_modules) > len(baseline), "DBSAMIZDAT_MODULES should add samizdats"

        # Should include samizdats from test_samizdats module
        from sample_app.test_samizdats import DealFruitFun, DealFruitView, PetUppercase

        assert DealFruitView in with_modules, "Should include DealFruitView from DBSAMIZDAT_MODULES"
        assert DealFruitFun in with_modules, "Should include DealFruitFun from DBSAMIZDAT_MODULES"
        assert PetUppercase in with_modules, "Should include PetUppercase from DBSAMIZDAT_MODULES"

        # Should still include samizdats from installed apps
        assert AView in with_modules, "Should still include samizdats from installed apps"
        assert ExampleTable in with_modules, "Should still include samizdats from installed apps"
    finally:
        # Restore original setting
        if original_modules:
            settings.DBSAMIZDAT_MODULES = original_modules
        elif hasattr(settings, "DBSAMIZDAT_MODULES"):
            delattr(settings, "DBSAMIZDAT_MODULES")


@pytest.mark.django
def test_autodiscover_multiple_dbsamizdat_modules(django_setup):
    """
    Test that autodiscover handles multiple modules in DBSAMIZDAT_MODULES.

    Requires Django to be configured.
    """
    from django.conf import settings

    from dbsamizdat.loader import autodiscover_samizdats

    original_modules = getattr(settings, "DBSAMIZDAT_MODULES", [])
    try:
        # Set multiple modules
        settings.DBSAMIZDAT_MODULES = [
            "sample_app.test_samizdats",
            "sample_app.dbsamizdat_defs",  # This is already autodiscovered, but should work
        ]
        result = set(autodiscover_samizdats())

        # Should include samizdats from both modules
        from sample_app.dbsamizdat_defs import AView
        from sample_app.test_samizdats import DealFruitView

        assert DealFruitView in result, "Should include samizdats from first module"
        assert AView in result, "Should include samizdats from second module"
    finally:
        # Restore original setting
        if original_modules:
            settings.DBSAMIZDAT_MODULES = original_modules
        elif hasattr(settings, "DBSAMIZDAT_MODULES"):
            delattr(settings, "DBSAMIZDAT_MODULES")


@pytest.mark.django
def test_autodiscover_empty_dbsamizdat_modules(django_setup):
    """
    Test that autodiscover works when DBSAMIZDAT_MODULES is empty.

    Requires Django to be configured.
    """
    from django.conf import settings

    from dbsamizdat.loader import autodiscover_samizdats

    original_modules = getattr(settings, "DBSAMIZDAT_MODULES", [])
    try:
        # Set empty list
        settings.DBSAMIZDAT_MODULES = []
        result = list(autodiscover_samizdats())

        # Should still work and return samizdats from installed apps
        assert isinstance(result, list)
        assert len(result) > 0, "Should still find samizdats from installed apps"
    finally:
        # Restore original setting
        if original_modules:
            settings.DBSAMIZDAT_MODULES = original_modules
        elif hasattr(settings, "DBSAMIZDAT_MODULES"):
            delattr(settings, "DBSAMIZDAT_MODULES")


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
