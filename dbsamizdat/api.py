"""
API for using dbsamizdat as a library
"""

import os
from collections.abc import Iterable

from .runner import ArgType
from .runner import cmd_nuke as _cmd_nuke
from .runner import cmd_refresh as _cmd_refresh
from .runner import cmd_sync as _cmd_sync
from .runner import txstyle
from .samizdat import Samizdat

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

DEFAULT_URL = os.environ.get("DBURL")

_CMD_ARG_DEFAULTS = dict(
    log_rather_than_print=True,
    in_django=False,
    verbosity=1,
)


def refresh(
    dburl: str | None = DEFAULT_URL,
    transaction_style: txstyle = txstyle.JUMBO,
    belownodes: Iterable[str | tuple | Samizdat] = tuple(),
    samizdatmodules: list[str] | None = None,
):
    """
    Refresh materialized views, in dependency order, optionally restricted
    to views depending directly or transitively on any of the DB objects specified
    in `belownodes`.
    
    Args:
        dburl: PostgreSQL connection string (defaults to DBURL env var)
        transaction_style: Transaction discipline (default: JUMBO)
        belownodes: Filter to refresh only views depending on these nodes
        samizdatmodules: Optional list of module names to import and search for samizdats
    
    Example:
        >>> from dbsamizdat import refresh
        >>> refresh("postgresql:///mydb", samizdatmodules=["myapp.views"])
    """
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dburl=dburl or DEFAULT_URL,
        txdiscipline=transaction_style.value,
        belownodes=belownodes,
        samizdatmodules=samizdatmodules or [],
    )
    _cmd_refresh(args)


def sync(
    dburl: str | None = DEFAULT_URL,
    transaction_style: txstyle = txstyle.JUMBO,
    samizdatmodules: list[str] | None = None,
):
    """
    Sync dbsamizdat state to the DB.
    
    Args:
        dburl: PostgreSQL connection string (defaults to DBURL env var)
        transaction_style: Transaction discipline (default: JUMBO)
        samizdatmodules: Optional list of module names to import and search for samizdats
    
    Example:
        >>> from dbsamizdat import sync
        >>> sync("postgresql:///mydb", samizdatmodules=["myapp.views", "myapp.models"])
    """
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dburl=dburl or DEFAULT_URL,
        txdiscipline=transaction_style.value,
        samizdatmodules=samizdatmodules or [],
    )
    _cmd_sync(args)


def nuke(
    dburl: str | None = DEFAULT_URL,
    transaction_style: txstyle = txstyle.JUMBO,
    samizdatmodules: list[str] | None = None,
):
    """
    Remove any database object tagged as samizdat.
    
    Args:
        dburl: PostgreSQL connection string (defaults to DBURL env var)
        transaction_style: Transaction discipline (default: JUMBO)
        samizdatmodules: Optional list of module names to import and search for samizdats
    
    Example:
        >>> from dbsamizdat import nuke
        >>> nuke("postgresql:///mydb", samizdatmodules=["myapp.views"])
    """
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dburl=dburl or DEFAULT_URL,
        txdiscipline=transaction_style.value,
        samizdatmodules=samizdatmodules or [],
    )
    _cmd_nuke(args)
