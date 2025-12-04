"""
Type definitions for runner module.

This module contains type definitions and configuration classes
used throughout the runner package.
"""

import argparse
import os
from collections.abc import Iterable
from enum import Enum
from typing import Literal


class txstyle(Enum):
    """
    Transaction discipline styles for database operations.

    - CHECKPOINT: Commit after each action
    - JUMBO: One large transaction for all actions
    - DRYRUN: Rollback all changes (for testing)
    """

    CHECKPOINT = "checkpoint"
    JUMBO = "jumbo"
    DRYRUN = "dryrun"


type ACTION = Literal["create", "nuke", "update", "refresh", "drop", "sign"]


class ArgType(argparse.Namespace):
    """
    Namespace for command-line arguments and API parameters.

    Attributes:
        txdiscipline: Transaction style (checkpoint/jumbo/dryrun)
        verbosity: Output verbosity level (0=quiet, 1=normal, 2=verbose)
        belownodes: Filter to refresh only views depending on these nodes
        in_django: Whether running in Django context
        log_rather_than_print: Use logging instead of print statements
        dbconn: Django database connection name
        dburl: PostgreSQL connection string
        samizdatmodules: List of module names containing samizdat classes
    """

    txdiscipline: Literal["checkpoint", "jumbo", "dryrun"] | None = "dryrun"
    verbosity: int = 1
    belownodes: Iterable[str] = []
    in_django: bool = False
    log_rather_than_print: bool = True
    dbconn: str = "default"
    dburl: str | None = os.environ.get("DBURL")
    samizdatmodules: list[str] = []
