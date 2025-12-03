"""Tests for library API functions in dbsamizdat.api"""

import os
from unittest.mock import MagicMock, patch

import pytest

from dbsamizdat.api import nuke, refresh, sync
from dbsamizdat.runner import txstyle


@pytest.mark.unit
def test_sync_with_module_names():
    """Test sync() function with samizdatmodules parameter"""
    with patch("dbsamizdat.api._cmd_sync") as mock_sync:
        sync("postgresql:///test", samizdatmodules=["myapp.views"])
        mock_sync.assert_called_once()
        args = mock_sync.call_args[0][0]
        assert args.samizdatmodules == ["myapp.views"]
        assert args.dburl == "postgresql:///test"
        assert args.txdiscipline == txstyle.JUMBO.value


@pytest.mark.unit
def test_sync_with_transaction_style():
    """Test sync() function with custom transaction style"""
    with patch("dbsamizdat.api._cmd_sync") as mock_sync:
        sync("postgresql:///test", transaction_style=txstyle.CHECKPOINT)
        args = mock_sync.call_args[0][0]
        assert args.txdiscipline == txstyle.CHECKPOINT.value


@pytest.mark.unit
def test_refresh_with_belownodes():
    """Test refresh() with belownodes filter"""
    with patch("dbsamizdat.api._cmd_refresh") as mock_refresh:
        refresh("postgresql:///test", belownodes=["users", "orders"])
        args = mock_refresh.call_args[0][0]
        assert "users" in args.belownodes
        assert "orders" in args.belownodes


@pytest.mark.unit
def test_refresh_with_module_names():
    """Test refresh() with samizdatmodules parameter"""
    with patch("dbsamizdat.api._cmd_refresh") as mock_refresh:
        refresh("postgresql:///test", samizdatmodules=["myapp.views"])
        args = mock_refresh.call_args[0][0]
        assert args.samizdatmodules == ["myapp.views"]


@pytest.mark.unit
def test_nuke_function():
    """Test nuke() function"""
    with patch("dbsamizdat.api._cmd_nuke") as mock_nuke:
        nuke("postgresql:///test")
        mock_nuke.assert_called_once()
        args = mock_nuke.call_args[0][0]
        assert args.dburl == "postgresql:///test"


@pytest.mark.unit
def test_nuke_with_module_names():
    """Test nuke() with samizdatmodules parameter"""
    with patch("dbsamizdat.api._cmd_nuke") as mock_nuke:
        nuke("postgresql:///test", samizdatmodules=["myapp.views"])
        args = mock_nuke.call_args[0][0]
        assert args.samizdatmodules == ["myapp.views"]


@pytest.mark.unit
def test_api_functions_use_default_dburl():
    """Test that API functions use DBURL env var when dburl not provided"""
    original_dburl = os.environ.get("DBURL")
    try:
        os.environ["DBURL"] = "postgresql:///default"
        # Need to reload the module to pick up new env var
        import importlib
        import dbsamizdat.api
        importlib.reload(dbsamizdat.api)
        from dbsamizdat.api import sync as reloaded_sync
        
        with patch("dbsamizdat.api._cmd_sync") as mock_sync:
            reloaded_sync()
            args = mock_sync.call_args[0][0]
            assert args.dburl == "postgresql:///default"
    finally:
        if original_dburl:
            os.environ["DBURL"] = original_dburl
        elif "DBURL" in os.environ:
            del os.environ["DBURL"]
        # Reload module to restore original state
        import importlib
        import dbsamizdat.api
        importlib.reload(dbsamizdat.api)


@pytest.mark.unit
def test_api_functions_use_provided_dburl_over_env():
    """Test that provided dburl takes precedence over DBURL env var"""
    original_dburl = os.environ.get("DBURL")
    try:
        os.environ["DBURL"] = "postgresql:///env"
        with patch("dbsamizdat.api._cmd_sync") as mock_sync:
            sync("postgresql:///provided")
            args = mock_sync.call_args[0][0]
            assert args.dburl == "postgresql:///provided"
    finally:
        if original_dburl:
            os.environ["DBURL"] = original_dburl
        elif "DBURL" in os.environ:
            del os.environ["DBURL"]


@pytest.mark.unit
def test_api_functions_with_none_dburl():
    """Test that API functions handle None dburl"""
    original_dburl = os.environ.get("DBURL")
    try:
        if "DBURL" in os.environ:
            del os.environ["DBURL"]
        with patch("dbsamizdat.api._cmd_sync") as mock_sync:
            sync(None)
            args = mock_sync.call_args[0][0]
            # Should use DEFAULT_URL which is None when DBURL not set
            assert args.dburl is None
    finally:
        if original_dburl:
            os.environ["DBURL"] = original_dburl


@pytest.mark.unit
def test_refresh_with_samizdat_belownodes():
    """Test refresh() with Samizdat objects as belownodes"""
    from dbsamizdat import SamizdatView

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    with patch("dbsamizdat.api._cmd_refresh") as mock_refresh:
        refresh("postgresql:///test", belownodes=[TestView])
        args = mock_refresh.call_args[0][0]
        assert TestView in args.belownodes


@pytest.mark.unit
def test_api_functions_default_verbosity():
    """Test that API functions use default verbosity settings"""
    with patch("dbsamizdat.api._cmd_sync") as mock_sync:
        sync("postgresql:///test")
        args = mock_sync.call_args[0][0]
        assert args.verbosity == 1
        assert args.log_rather_than_print is True
        assert args.in_django is False

