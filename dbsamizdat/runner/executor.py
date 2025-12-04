"""
Command execution engine for runner.

This module contains the core executor that runs database commands
with progress reporting, error handling, and transaction savepoints.
"""

from collections.abc import Iterable

from ..exceptions import DatabaseError, FunctionSignatureError
from ..libdb import get_dbstate
from ..loader import SamizType
from ..samtypes import Cursor
from ..util import sqlfmt
from .helpers import timer, vprint
from .types import ACTION, ArgType, txstyle


def executor(
    yielder: Iterable[tuple[ACTION, SamizType, str]],
    args: ArgType,
    cursor: Cursor,
    max_namelen=0,
    timing=False,
):
    """
    Execute a series of database actions with progress reporting.

    Args:
        yielder: Iterator of (action, samizdat, sql) tuples
        args: ArgType with verbosity and transaction settings
        cursor: Database cursor for execution
        max_namelen: Max name length for formatting (0 = no formatting)
        timing: Whether to show timing information

    Raises:
        DatabaseError: If SQL execution fails
        FunctionSignatureError: If function signature doesn't match

    Features:
        - Progress reporting with optional timing
        - Savepoints for individual action rollback
        - Special handling for function signature errors
        - Transaction checkpointing support

    Example:
        >>> def actions():
        ...     yield "create", MyView, MyView.create()
        ...     yield "sign", MyView, MyView.sign(cursor)
        >>> executor(actions(), args, cursor, timing=True)
    """
    action_timer = timer()
    next(action_timer)

    def progressprint(ix, action_totake, sd: SamizType, sql):
        if args.verbosity:
            if ix:
                # print the processing time of the *previous* action
                vprint(args, f"{next(action_timer):.2f}s" if timing else "")
            vprint(
                args,
                f"%-7s %-17s %-{max_namelen}s ..." % (action_totake, sd.entity_type.value, sd),
                end="",
            )
            vprint(args, f"\n\n{sqlfmt(sql)}\n\n")

    action_cnt = 0
    for ix, progress in enumerate(yielder):
        action_cnt += 1
        progressprint(ix, *progress)
        action_totake, sd, sql = progress
        try:
            try:
                cursor.execute("BEGIN;")  # harmless if already in a tx but raises a warning
                cursor.execute(f"SAVEPOINT action_{action_totake};")
                cursor.execute(sql)
            except Exception as ouch:
                if action_totake == "sign":
                    cursor.execute(f"ROLLBACK TO SAVEPOINT action_{action_totake};")  # get back to a non-error state
                    candidate_args = [
                        c[3] for c in get_dbstate(cursor) if c[:2] == (sd.schema, getattr(sd, "function_name", ""))
                    ]
                    raise FunctionSignatureError(sd, candidate_args)
                raise ouch
        except Exception as dberr:
            raise DatabaseError(f"{action_totake} failed", dberr, sd, sql)
        cursor.execute(f"RELEASE SAVEPOINT action_{action_totake};")
        if args.txdiscipline == txstyle.CHECKPOINT.value and action_totake != "create":
            # only commit *after* signing, otherwise if later the signing somehow fails
            # we'll have created an orphan DB object that we don't recognize as ours
            cursor.execute("COMMIT;")

    if action_cnt:
        vprint(args, f"{next(action_timer):.2f}s" if timing else "")
