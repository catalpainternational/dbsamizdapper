from importlib import import_module

from dbsamizdat.loader import samizdats_in_app, samizdats_in_module
from sample_app.dbsamizdat_defs import AView


def test_load_from_module():
    m = import_module("sample_app.test_samizdats")
    list(samizdats_in_module(m))


def test_import_from_app():
    assert set(samizdats_in_app("sample_app")) == {AView}


def test_autodiscover():
    # TODO: Make this pass by setting up Django app properly
    # list(autodiscover_samizdats())
    ...
