"""
Runner package for dbsamizdat command execution.

This package is being refactored from a monolithic runner.py module
into separate focused modules for better maintainability.

Structure:
    helpers.py - Utility functions (vprint, timer, get_sds)
    context.py - Database context management (get_cursor, txi_finalize) [TODO]
    executor.py - Command execution engine (executor) [TODO]
    commands.py - Command implementations (cmd_*) [TODO]
    cli.py - CLI argument parsing (augment_argument_parser, main) [TODO]

Backward Compatibility:
    All functions remain importable from dbsamizdat.runner for compatibility.
"""

# Import remaining items from the old monolithic runner.py
# These live at dbsamizdat/runner.py (sibling to the runner/ package directory)
import importlib.util
from pathlib import Path

# Import from new modular structure
from .helpers import get_sds, timer, vprint

# Load the old _runner.py module (temporarily renamed to avoid shadowing)
_runner_py_path = Path(__file__).parent.parent / "_runner.py"

if _runner_py_path.exists():
    spec = importlib.util.spec_from_file_location("_dbsamizdat_runner_old", _runner_py_path)
    if spec and spec.loader:
        _old_runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_old_runner)

        # Re-export types and enums
        ArgType = _old_runner.ArgType
        txstyle = _old_runner.txstyle
        ACTION = _old_runner.ACTION

        # Re-export context management (to be moved to context.py)
        get_cursor = _old_runner.get_cursor
        txi_finalize = _old_runner.txi_finalize

        # Re-export executor (to be moved to executor.py)
        executor = _old_runner.executor

        # Re-export commands (to be moved to commands.py)
        cmd_sync = _old_runner.cmd_sync
        cmd_refresh = _old_runner.cmd_refresh
        cmd_nuke = _old_runner.cmd_nuke
        cmd_diff = _old_runner.cmd_diff
        cmd_printdot = _old_runner.cmd_printdot

        # Re-export CLI (to be moved to cli.py)
        augment_argument_parser = _old_runner.augment_argument_parser
        main = _old_runner.main
else:
    # runner.py doesn't exist - migration is complete
    # All imports should come from submodules
    raise ImportError("Migration incomplete: runner.py not found and not all modules extracted")

__all__ = [
    # Helpers (already extracted)
    "vprint",
    "timer",
    "get_sds",
    # Types
    "ArgType",
    "txstyle",
    "ACTION",
    # Context management (to be extracted)
    "get_cursor",
    "txi_finalize",
    # Executor (to be extracted)
    "executor",
    # Commands (to be extracted)
    "cmd_sync",
    "cmd_refresh",
    "cmd_nuke",
    "cmd_diff",
    "cmd_printdot",
    # CLI (to be extracted)
    "augment_argument_parser",
    "main",
]
