"""
Runner package for dbsamizdat command execution.

This package was refactored from a monolithic runner.py module (446 lines)
into focused modules for better maintainability and testability.

Modules:
    types.py - Type definitions (ArgType, txstyle, ACTION)
    helpers.py - Utility functions (vprint, timer, get_sds)
    context.py - Database connection management (get_cursor, txi_finalize)
    executor.py - Command execution engine (executor)
    commands.py - Command implementations (cmd_*)
    cli.py - CLI argument parsing (augment_argument_parser, main)

Backward Compatibility:
    All functions remain importable from dbsamizdat.runner:
    >>> from dbsamizdat.runner import cmd_sync, ArgType

    Or from specific modules:
    >>> from dbsamizdat.runner.commands import cmd_sync
    >>> from dbsamizdat.runner.types import ArgType
"""

# Import from new modular structure
from .cli import augment_argument_parser, main
from .commands import cmd_diff, cmd_nuke, cmd_printdot, cmd_refresh, cmd_sync
from .context import get_cursor, txi_finalize
from .executor import executor
from .helpers import get_sds, timer, vprint
from .types import ACTION, ArgType, txstyle

__all__ = [
    # Types and enums
    "ArgType",
    "txstyle",
    "ACTION",
    # Helpers
    "vprint",
    "timer",
    "get_sds",
    # Context management
    "get_cursor",
    "txi_finalize",
    # Executor
    "executor",
    # Commands
    "cmd_sync",
    "cmd_refresh",
    "cmd_nuke",
    "cmd_diff",
    "cmd_printdot",
    # CLI
    "augment_argument_parser",
    "main",
]
