from importlib import import_module
from dbsamizdat.dbsamizdat_defs import AView
from dbsamizdat.loader import samizdats_in_app, samizdats_in_module


def test_load_from_module():
    m = import_module("dbsamizdat.test_samizdats")
    x = list(samizdats_in_module(m))
    print(x)


def test_import_from_app():
    assert set(samizdats_in_app("dbsamizdat")) == {AView}


def test_autodiscover():
    # TODO: Make this pass by setting up Django app properly
    # list(autodiscover_samizdats())
    ...
