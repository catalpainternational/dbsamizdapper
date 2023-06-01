"""
API for using dbsamizdat as a library
"""

import os
from typing import Iterable, Union

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
    belownodes: Iterable[Union[str, tuple, Samizdat]] = tuple(),
):
    """
    Refresh materialized views, in dependency order, optionally restricted
    to views depending directly or transitively on any of the DB objects specified
    in `belownodes`."""
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dburl=dburl or DEFAULT_URL,
        txdiscipline=transaction_style.value,
        belownodes=belownodes,
    )
    _cmd_refresh(args)


def sync(
    dburl: str | None = DEFAULT_URL,
    transaction_style: txstyle = txstyle.JUMBO,
):
    """Sync dbsamizdat state to the DB."""
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dburl=dburl or DEFAULT_URL,
        txdiscipline=transaction_style.value,
    )
    _cmd_sync(args)


def nuke(dburl: str | None = DEFAULT_URL, transaction_style: txstyle = txstyle.JUMBO):
    """Remove any database object tagged as samizdat."""
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dburl=dburl or DEFAULT_URL,
        txdiscipline=transaction_style.value,
    )
    _cmd_nuke(args)
