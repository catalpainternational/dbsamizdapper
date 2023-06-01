"""
API for using dbsamizdat as a library in Django
"""

from typing import Iterable, Union

from .runner import ArgType
from .runner import cmd_nuke as _cmd_nuke
from .runner import cmd_refresh as _cmd_refresh
from .runner import cmd_sync as _cmd_sync
from .runner import txstyle
from .samizdat import Samizdat

_CMD_ARG_DEFAULTS = dict(
    in_django=True,
    verbosity=1,
    log_rather_than_print=True,
)


def refresh(
    dbconn: str = "default",
    transaction_style: txstyle = txstyle.JUMBO,
    belownodes: Iterable[Union[str, tuple, Samizdat]] = tuple(),
    samizdatmodules=tuple(),
):
    """Refresh materialized views, in dependency order, optionally restricted to views depending directly or transitively on any of the DB objects specified in `belownodes`."""  # noqa: E501
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dbconn=dbconn,
        txdiscipline=transaction_style.value,
        belownodes=belownodes,
        samizdatmodules=samizdatmodules,
    )
    _cmd_refresh(args)


def sync(
    dbconn: str = "default",
    transaction_style: txstyle = txstyle.JUMBO,
    samizdatmodules=tuple(),
):
    """Sync dbsamizdat state to the DB."""
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dbconn=dbconn,
        txdiscipline=transaction_style.value,
        samizdatmodules=samizdatmodules,
    )
    _cmd_sync(args)


def nuke(
    dbconn: str = "default",
    transaction_style: txstyle = txstyle.JUMBO,
    samizdatmodules=tuple(),
):
    """Remove any database object tagged as samizdat."""
    args = ArgType(
        **_CMD_ARG_DEFAULTS,
        dbconn=dbconn,
        txdiscipline=transaction_style.value,
        samizdatmodules=samizdatmodules,
    )
    _cmd_nuke(args)
