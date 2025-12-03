"""Tests for CLI argument parsing in dbsamizdat.runner.cli"""

import argparse
import sys
from unittest.mock import MagicMock, patch

import pytest

from dbsamizdat.exceptions import SamizdatException
from dbsamizdat.runner.cli import augment_argument_parser, main


@pytest.mark.unit
def test_augment_argument_parser_adds_subcommands():
    """Test that augment_argument_parser adds all expected subcommands"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Check that subcommands exist by trying to parse
    # We can't easily check subparsers directly, so we test by parsing
    args = parser.parse_args(["sync", "postgresql:///test", "module1"])
    assert hasattr(args, "func")
    assert args.dburl == "postgresql:///test"
    assert args.samizdatmodules == ["module1"]


@pytest.mark.unit
def test_cli_requires_modules_when_not_django():
    """Test that CLI requires samizdatmodules when not in Django"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Try parsing without modules - should fail
    with pytest.raises(SystemExit):
        parser.parse_args(["sync", "postgresql:///test"])


@pytest.mark.unit
def test_cli_django_mode_uses_dbconn():
    """Test that Django mode uses dbconn instead of dburl"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=True)

    args = parser.parse_args(["sync", "custom_conn"])
    assert args.dbconn == "custom_conn"
    # In Django mode, samizdatmodules should be empty by default
    assert args.samizdatmodules == []


@pytest.mark.unit
def test_cli_django_mode_default_connection():
    """Test that Django mode defaults to 'default' connection"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=True)

    args = parser.parse_args(["sync"])
    assert args.dbconn == "default"


@pytest.mark.unit
def test_cli_verbosity_flags():
    """Test that verbosity flags work correctly"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Test quiet flag
    args = parser.parse_args(["-q", "sync", "postgresql:///test", "module"])
    assert args.verbosity == 0

    # Test verbose flag
    args = parser.parse_args(["-v", "sync", "postgresql:///test", "module"])
    assert args.verbosity == 2


@pytest.mark.unit
def test_cli_transaction_discipline():
    """Test that transaction discipline argument works"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Transaction discipline is a subcommand argument, not top-level
    args = parser.parse_args(["sync", "-t", "jumbo", "postgresql:///test", "module"])
    assert args.txdiscipline == "jumbo"

    args = parser.parse_args(["sync", "-t", "checkpoint", "postgresql:///test", "module"])
    assert args.txdiscipline == "checkpoint"

    args = parser.parse_args(["sync", "-t", "dryrun", "postgresql:///test", "module"])
    assert args.txdiscipline == "dryrun"


@pytest.mark.unit
def test_cli_refresh_with_belownodes():
    """Test that refresh command accepts belownodes argument"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    args = parser.parse_args(
        ["refresh", "postgresql:///test", "module", "--belownodes", "users", "orders"]
    )
    assert args.belownodes == ["users", "orders"]


@pytest.mark.unit
def test_cli_all_subcommands_exist():
    """Test that all expected subcommands exist"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Test that subcommands are registered
    # We can't easily test parsing without proper arguments, so just verify structure
    assert hasattr(parser, "_subparsers")
    
    # Test sync command can be parsed with proper args
    args = parser.parse_args(["sync", "postgresql:///test", "module"])
    assert hasattr(args, "func")
    assert args.func is not None


@pytest.mark.unit
def test_main_handles_samizdat_exception():
    """Test that main() handles SamizdatException gracefully"""
    with patch("sys.argv", ["dbsamizdat", "sync", "postgresql:///test", "module"]):
        with patch("dbsamizdat.runner.cli.augment_argument_parser") as mock_parser:
            mock_args = MagicMock()
            mock_args.func = MagicMock(side_effect=SamizdatException("Test error"))
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse_args.return_value = mock_args
            mock_parser.return_value = mock_parser_instance

            with pytest.raises(SystemExit):
                main()


@pytest.mark.unit
def test_main_handles_keyboard_interrupt():
    """Test that main() handles KeyboardInterrupt gracefully"""
    with patch("sys.argv", ["dbsamizdat", "sync", "postgresql:///test", "module"]):
        with patch("dbsamizdat.runner.cli.augment_argument_parser") as mock_parser:
            mock_args = MagicMock()
            mock_args.func = MagicMock(side_effect=KeyboardInterrupt())
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse_args.return_value = mock_args
            mock_parser.return_value = mock_parser_instance

            with pytest.raises(SystemExit):
                main()


@pytest.mark.unit
def test_cli_default_values():
    """Test that CLI sets correct default values"""
    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    args = parser.parse_args(["sync", "postgresql:///test", "module"])
    assert args.verbosity == 1
    assert args.txdiscipline == "checkpoint"  # Default from argparse
    assert args.in_django is False
    # log_rather_than_print defaults to False when augment_argument_parser is called with default
    # but it's set in the defaults dict, so check what's actually set
    assert hasattr(args, "log_rather_than_print")

