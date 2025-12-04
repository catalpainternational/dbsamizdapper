"""
Command implementations for dbsamizdat runner.

This module contains all the cmd_* command implementations:
- cmd_sync: Synchronize database state
- cmd_refresh: Refresh materialized views
- cmd_nuke: Drop all dbsamizdat objects
- cmd_diff: Show differences between DB and code
- cmd_printdot: Print dependency graph
"""

from collections.abc import Iterable

from ..graphvizdot import dot
from ..libdb import dbinfo_to_class, dbstate_equals_definedstate, get_dbstate
from ..libgraph import node_dump, subtree_depends
from ..loader import SamizType
from ..samizdat import sd_is_matview
from ..samtypes import FQTuple
from ..util import nodenamefmt
from .context import get_cursor
from .executor import executor
from .helpers import get_sds, vprint
from .types import ArgType


def cmd_refresh(args: ArgType):
    """
    Refresh materialized views in dependency order.

    Args:
        args: ArgType with optional belownodes filter

    Behavior:
        - Discovers all materialized views
        - Optionally filters to subtree of belownodes
        - Refreshes in dependency order
        - Uses concurrent refresh when allowed
    """
    with get_cursor(args) as cursor:
        samizdats = get_sds(args.in_django, samizdatmodules=getattr(args, "samizdatmodules", None) or [])
        matviews = [sd for sd in samizdats if sd_is_matview(sd)]

        if args.belownodes:
            rootnodes = {FQTuple.fqify(rootnode) for rootnode in args.belownodes}
            allnodes = node_dump(samizdats)
            if rootnodes - allnodes:
                raise ValueError(
                    """Unknown rootnodes:\n\t- {}""".format(
                        "\n\t- ".join([nodenamefmt(rootnode) for rootnode in rootnodes - allnodes])
                    )
                )
            subtree_bundle = subtree_depends(samizdats, rootnodes)
            matviews = [sd for sd in matviews if sd in subtree_bundle]

        # Filter to only materialized views that exist in the database
        # This prevents errors when code defines matviews that haven't been synced
        db_matviews = {
            FQTuple.fqify((s.schemaname, s.viewname)) for s in get_dbstate(cursor) if s.objecttype == "MATVIEW"
        }
        matviews = [sd for sd in matviews if sd.fq() in db_matviews]

        max_namelen = max(len(str(ds)) for ds in matviews) if len(matviews) else 50

        def refreshes():
            for sd in matviews:
                yield "refresh", sd, sd.refresh(concurrent_allowed=True)

        executor(refreshes(), args, cursor, max_namelen=max_namelen, timing=True)


def cmd_sync(args: ArgType, samizdatsIn: list[SamizType] | None = None):
    """
    Synchronize database state with code definitions.

    Args:
        args: ArgType with database connection info
        samizdatsIn: Optional explicit list of samizdats to sync

    Behavior:
        - Compares DB state to code definitions
        - Drops excess DB objects
        - Creates missing objects
        - Refreshes new materialized views

    Note:
        Uses cascade drops so order doesn't matter.
        Re-reads DB state after drops due to cascading effects.
    """
    samizdatmodules = getattr(args, "samizdatmodules", None) or []
    samizdats = tuple(get_sds(False, samizdatsIn, samizdatmodules)) or tuple(
        get_sds(args.in_django, samizdatmodules=samizdatmodules)
    )

    with get_cursor(args) as cursor:
        db_compare = dbstate_equals_definedstate(cursor, samizdats)
        if db_compare.issame:
            vprint(args, "No differences, nothing to do.")
            return

        # Get the longest name from what's in the
        # database and defined state
        max_namelen = max(len(str(ds)) for ds in db_compare.excess_dbstate | db_compare.excess_definedstate)

        def drops():
            for sd in db_compare.excess_dbstate:
                yield "drop", sd, sd.drop(if_exists=True)
                # we don't know the deptree; so they may have vanished
                # through a cascading drop of a previous object

        executor(drops(), args, cursor, max_namelen=max_namelen, timing=True)
        db_compare = dbstate_equals_definedstate(cursor, samizdats)
        # again, we don't know the in-db deptree, so we need to re-read DB
        # state as the rug may have been pulled out from under us with cascading
        # drops

        def creates():
            to_create_ids = {sd.head_id() for sd in db_compare.excess_definedstate}

            for sd in samizdats:  # iterate in proper creation order
                if sd.head_id() not in to_create_ids:
                    continue
                yield "create", sd, sd.create()
                yield "sign", sd, sd.sign(cursor)

        executor(creates(), args, cursor, max_namelen=max_namelen, timing=True)

        def refreshes():
            for sd in filter(sd_is_matview, samizdats):
                if sd not in db_compare.excess_definedstate:
                    continue
                yield "refresh", sd, sd.refresh(concurrent_allowed=False)

        executor(refreshes(), args, cursor, max_namelen=max_namelen, timing=True)


def cmd_diff(args: ArgType):
    """
    Show differences between database and code state.

    Args:
        args: ArgType with database connection info

    Behavior:
        - Compares DB state to code definitions
        - Prints excess DB objects
        - Prints excess code definitions
        - Exits with code indicating type of differences

    Exit Codes:
        0: No differences
        101: Excess DB objects only
        102: Excess code definitions only
        103: Both have excess objects
    """
    with get_cursor(args) as cursor:
        samizdatmodules = getattr(args, "samizdatmodules", None) or []
        samizdats = get_sds(args.in_django, samizdatmodules=samizdatmodules)
        db_compare = dbstate_equals_definedstate(cursor, samizdats)
        if db_compare.issame:
            vprint(args, "No differences.")
            exit(0)

        max_namelen = max(len(str(ds)) for ds in db_compare.excess_dbstate | db_compare.excess_definedstate)

        def statefmt(state: Iterable[SamizType], prefix):
            return "\n".join(
                f"%s%-17s\t%-{max_namelen}s\t%s" % (prefix, sd.entity_type.value, sd, sd.definition_hash())
                for sd in sorted(state, key=lambda sd: str(sd))
            )

        if db_compare.excess_dbstate:
            vprint(
                args,
                statefmt(db_compare.excess_dbstate, "Not in samizdats:\t"),
            )
        if db_compare.excess_definedstate:
            vprint(
                args,
                statefmt(db_compare.excess_definedstate, "Not in database:   \t"),
            )

    # Exit code depends on the database state and
    # defined state
    exitcode = 100
    exitflag = 0

    if db_compare.excess_dbstate:
        exitflag | +1
    if db_compare.excess_definedstate:
        exitflag | +2

    exit(exitcode + exitflag)


def cmd_printdot(args: ArgType):
    """
    Print dependency graph in GraphViz DOT format.

    Args:
        args: ArgType (uses in_django to determine discovery method)

    Output:
        Prints DOT format to stdout for piping to graphviz tools

    Example:
        $ dbsamizdat printdot | dot -Tpng > graph.png
    """
    samizdatmodules = getattr(args, "samizdatmodules", None) or []
    print("\n".join(dot(get_sds(args.in_django, samizdatmodules=samizdatmodules))))


def cmd_nuke(args: ArgType, samizdats: list[SamizType] | None = None):
    """
    Drop all dbsamizdat-managed database objects.

    Args:
        args: ArgType with database connection info
        samizdats: Optional explicit list of samizdats to drop

    Behavior:
        - If samizdats provided: drops those
        - Otherwise: drops all objects found in DB with dbsamizdat comments
        - Uses IF EXISTS to avoid errors on cascaded drops

    Warning:
        This is destructive! Use with caution.
    """
    with get_cursor(args) as cursor:

        def nukes():
            # If "samizdats" is not defined fetch from the database

            if samizdats is not None:
                yield from (("nuke", sd, sd.drop(if_exists=True)) for sd in samizdats)

            # If "samizdats" is not defined fetch from the database
            for state in get_dbstate(cursor):
                if state.commentcontent is None:
                    continue
                sd = dbinfo_to_class(state)
                yield ("nuke", sd, sd.drop(if_exists=True))

        executor(nukes(), args, cursor)
