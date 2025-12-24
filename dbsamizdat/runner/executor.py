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
                    # First try get_dbstate (filters by comments - for already-signed functions)
                    candidate_args = [
                        c[3] for c in get_dbstate(cursor) if c[:2] == (sd.schema, getattr(sd, "function_name", ""))
                    ]
                    # If not found and this is a function, query pg_proc directly
                    # (for functions that were just created but not yet signed)
                    if not candidate_args and sd.entity_type.value == "FUNCTION":
                        cursor.execute(
                            """
                            SELECT pg_catalog.pg_get_function_identity_arguments(p.oid) AS args
                            FROM pg_catalog.pg_proc p
                            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                            WHERE n.nspname = %s
                              AND p.proname = %s
                              AND p.prokind NOT IN ('a', 'w', 'p')
                            """,
                            (sd.schema, getattr(sd, "function_name", sd.get_name())),
                        )
                        candidate_args = [row[0] for row in cursor.fetchall() if row[0]]
                    raise FunctionSignatureError(sd, candidate_args)
                raise ouch
        except Exception as dberr:
            # Capture template context for better error messages
            template = None
            substitutions = None

            if action_totake == "create" and hasattr(sd, "get_sql_template"):
                try:
                    template = sd.get_sql_template()
                    # Extract substitutions that were used
                    if hasattr(sd, "entity_type"):
                        from ..samizdat import sd_is_function, sd_is_matview, sd_is_trigger

                        substitutions = {}
                        if sd_is_function(sd):
                            substitutions = {
                                "preamble": f"CREATE {sd.entity_type.value} {sd.creation_identity()}",
                                "samizdatname": sd.db_object_identity(),
                            }
                        elif sd_is_trigger(sd):
                            from ..samtypes import FQTuple

                            target_table = FQTuple.fqify(sd.on_table).db_object_identity()
                            substitutions = {
                                "preamble": f"""CREATE {sd.entity_type.value} "{sd.get_name()}" {sd.condition} ON {target_table}""",
                                "samizdatname": sd.get_name(),
                            }
                        elif sd_is_matview(sd):
                            _AS = " AS "
                            opts = ["UNLOGGED "] if getattr(sd, "unlogged", False) else []
                            substitutions = {
                                "preamble": f"""CREATE {" ".join(opts)}{sd.entity_type.value} {sd.db_object_identity()}{_AS}""",
                                "postamble": "WITH NO DATA",
                                "samizdatname": sd.db_object_identity(),
                            }
                        else:
                            # For views and tables
                            _AS = "" if sd.entity_type.name == "TABLE" else " AS "
                            opts = ["UNLOGGED "] if getattr(sd, "unlogged", False) else []
                            substitutions = {
                                "preamble": f"""CREATE {" ".join(opts)}{sd.entity_type.value} {sd.db_object_identity()}{_AS}""",
                                "postamble": "",
                                "samizdatname": sd.db_object_identity(),
                            }
                except Exception:
                    # If we can't get template info, continue without it
                    pass

            raise DatabaseError(f"{action_totake} failed", dberr, sd, sql, template, substitutions)
        cursor.execute(f"RELEASE SAVEPOINT action_{action_totake};")
        if args.txdiscipline == txstyle.CHECKPOINT.value and action_totake != "create":
            # only commit *after* signing, otherwise if later the signing somehow fails
            # we'll have created an orphan DB object that we don't recognize as ours
            cursor.execute("COMMIT;")

    if action_cnt:
        vprint(args, f"{next(action_timer):.2f}s" if timing else "")
