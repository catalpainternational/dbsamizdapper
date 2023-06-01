import argparse
import os
import sys
import typing
from contextlib import contextmanager
from enum import Enum
from importlib.util import find_spec
from logging import getLogger
from time import monotonic
from typing import Generator, Iterable, Literal, Type

import dotenv

from dbsamizdat.samizdat import Samizdat, SamizdatMaterializedView

from .exceptions import DatabaseError, FunctionSignatureError, SamizdatException
from .graphvizdot import dot
from .libdb import dbinfo_to_class, dbstate_equals_definedstate, get_dbstate
from .libgraph import depsort_with_sidekicks, node_dump, sanity_check, subtree_depends
from .loader import get_samizdats, autodiscover_samizdats
from .samtypes import Cursor, ProtoSamizdat, entitypes
from .util import fqify_node, nodenamefmt, sqlfmt

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser

dotenv.load_dotenv()


class txstyle(Enum):
    CHECKPOINT = "checkpoint"
    JUMBO = "jumbo"
    DRYRUN = "dryrun"


ACTION = Literal["create", "nuke", "update", "refresh", "drop", "sign"]

logger = getLogger(__name__)
PRINTKWARGS = dict(file=sys.stderr, flush=True)


class ArgType(argparse.Namespace):
    txdiscipline: Literal["checkpoint", "jumbo", "dryrun"] | None = "dryrun"
    verbosity: int = 1
    belownodes: Iterable[str] = []
    in_django: bool = False
    log_rather_than_print: bool = True
    dbconn: str = "default"
    dburl: str | None = os.environ.get("DBURL")


def vprint(args: ArgType, *pargs, **pkwargs):
    if args.log_rather_than_print:
        logger.info(" ".join(map(str, pargs)))
    elif args.verbosity:
        print(*pargs, **PRINTKWARGS, **pkwargs)


def timer() -> Generator[float, None, None]:
    """
    Generator to show time elapsed since the last iteration
    """
    last = monotonic()
    while True:
        cur = monotonic()
        yield (cur - last)
        last = cur


def get_sds(in_django: bool = False):
    if in_django:
        sds = list(autodiscover_samizdats())
    else:
        sds = get_samizdats()
    sanity_check(sds)
    return depsort_with_sidekicks(sds)

@contextmanager
def get_cursor(args: ArgType) -> Generator[Cursor, None, None]:
    """
    Returns a psycopg or Django cursor
    """

    dburl = getattr(args, "dburl", None)

    if args.in_django:
        from django.db import connections

        cursor = connections[args.dbconn].cursor().cursor

    elif not args.dburl:
        raise NotImplementedError("No dburl provided: nothing to do!")

    elif dburl and find_spec("psycopg"):
        import psycopg  # noqa: F811

        conn = psycopg.connect(dburl)
        cursor = psycopg.ClientCursor(conn)

    elif dburl and find_spec("psycopg2"):
        import psycopg2

        conn = psycopg2.connect(dburl)
        cursor = conn.cursor()

    cursor.execute("BEGIN;")
    yield cursor
    txi_finalize(cursor, getattr(args, "txdiscipline", "dryrun"))
    cursor.close()


def txi_finalize(cursor: Cursor, txdiscipline: Literal["jumbo", "dryrun", "checkpoint"]):
    """
    Executes a ROLLBACK if we're doing a dry run else a COMMIT
    """
    if txdiscipline == "jumbo":
        final_clause = "COMMIT;"
    elif txdiscipline == "dryrun":
        final_clause = "ROLLBACK;"
    elif txdiscipline == "checkpoint":
        final_clause = "COMMIT;"
    else:
        raise KeyError(f"Expected one of 'jumbo' or 'dryrun' or 'checkpoint'; got {txdiscipline}")
    cursor.execute(final_clause)


def cmd_refresh(args: ArgType):
    with get_cursor(args) as cursor:
        samizdats = get_sds(args.in_django)
        matviews: list[SamizdatMaterializedView] = [sd for sd in samizdats if sd.entity_type == entitypes.MATVIEW]

        if args.belownodes:
            rootnodes = {fqify_node(rootnode) for rootnode in args.belownodes}
            allnodes = node_dump(samizdats)
            if rootnodes - allnodes:
                raise ValueError(
                    """Unknown rootnodes:\n\t- %s"""
                    % "\n\t- ".join([nodenamefmt(rootnode) for rootnode in rootnodes - allnodes])
                )
            subtree_bundle = subtree_depends(samizdats, rootnodes)
            matviews = [sd for sd in matviews if sd in subtree_bundle]

        max_namelen = max(len(str(ds)) for ds in matviews) if len(matviews) else 50

        def refreshes():
            for sd in matviews:
                yield "refresh", sd, sd.refresh(concurrent_allowed=True)

        executor(refreshes(), args, cursor, max_namelen=max_namelen, timing=True)


def cmd_sync(args: ArgType):
    samizdats = get_sds(args.in_django)

    with get_cursor(args) as cursor:
        db_compare = dbstate_equals_definedstate(cursor, samizdats)
        if db_compare.issame:
            vprint(args, "No differences, nothing to do.")
            return
        max_namelen = max(len(str(ds)) for ds in db_compare.excess_dbstate | db_compare.excess_definedstate)
        if db_compare.excess_dbstate:

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
        if db_compare.excess_definedstate:

            def creates():
                to_create_ids = {sd.head_id() for sd in db_compare.excess_definedstate}
                for sd in samizdats:  # iterate in proper creation order
                    if sd.head_id() not in to_create_ids:
                        continue
                    yield "create", sd, sd.create()
                    yield "sign", sd, sd.sign(cursor)

            executor(creates(), args, cursor, max_namelen=max_namelen, timing=True)

            matviews_to_refresh = {
                sd.head_id() for sd in db_compare.excess_definedstate if sd.entity_type == entitypes.MATVIEW
            }
            if matviews_to_refresh:

                def refreshes():
                    for sd in samizdats:  # iterate in proper creation order
                        if sd.head_id() in matviews_to_refresh:
                            yield "refresh", sd, sd.refresh(concurrent_allowed=False)

                executor(refreshes(), args, cursor, max_namelen=max_namelen, timing=True)


def cmd_diff(args: ArgType):
    with get_cursor(args) as cursor:
        samizdats = get_sds(args.in_django)
        db_compare = dbstate_equals_definedstate(cursor, samizdats)
        if db_compare.issame:
            vprint(args, "No differences.")
            exit(0)

        max_namelen = max(len(str(ds)) for ds in db_compare.excess_dbstate | db_compare.excess_definedstate)

        def statefmt(state: Iterable[ProtoSamizdat], prefix):
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
    print("\n".join(dot(get_sds(args.in_django))))


def cmd_nuke(args: ArgType, samizdats: list[Samizdat] | None = None):
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


def executor(
    yielder: Iterable[tuple[ACTION, Samizdat | Type[ProtoSamizdat], str]],
    args: ArgType,
    cursor: Cursor,
    max_namelen=0,
    timing=False,
):
    action_timer = timer()
    next(action_timer)

    def progressprint(ix, action_totake, sd: Samizdat | Type[ProtoSamizdat], sql):
        if args.verbosity:
            if ix:
                # print the processing time of the *previous* action
                vprint(args, "%.2fs" % next(action_timer) if timing else "")
            vprint(
                args,
                f"%-7s %-17s %-{max_namelen}s ..." % (action_totake, sd.entity_type.value, sd),
                end="",
            )
            vprint(args, f"\n\n{sqlfmt(sql)}\n\n")

    action_cnt = 0
    for ix, progress in enumerate(yielder):
        action_cnt += 1
        try:
            progressprint(ix, *progress)
        except:
            raise
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
        vprint(args, "%.2fs" % next(action_timer) if timing else "")


def augment_argument_parser(p: "ArgumentParser", in_django=False, log_rather_than_print=True):
    def perhaps_add_modules_argument(parser):
        if not in_django:
            parser.add_argument(
                "samizdatmodules",
                nargs="+",
                help="Names of modules containing Samizdat subclasses",
            )

    def add_dbarg_argument(parser):
        if in_django:
            parser.add_argument(
                "dbconn",
                nargs="?",
                default="default",
                help="Django DB connection key (default:'default'). If you don't know what this is, then you don't need it.",  # noqa: E501
            )
        else:
            parser.add_argument(
                "dburl",
                help="PostgreSQL DB connection string. Trivially, this might be 'postgresql:///mydbname'. See https://www.postgresql.org/docs/14/static/libpq-connect.html#id-1.7.3.8.3.6 .",  # noqa: E501
            )

    def add_txdiscipline_argument(parser):
        parser.add_argument(
            "--txdiscipline",
            "-t",
            choices=(
                txstyle.CHECKPOINT.value,
                txstyle.JUMBO.value,
                txstyle.DRYRUN.value,
            ),
            default=txstyle.CHECKPOINT.value,
            help=f"""Transaction discipline. The "{txstyle.CHECKPOINT.value}" level commits after every dbsamizdat-level action. The safe default of "{txstyle.JUMBO.value}" creates one large transaction. "{txstyle.DRYRUN.value}" also creates one large transaction, but rolls it back.""",  # noqa: E501
        )

    p.set_defaults(
        **dict(
            func=lambda whatevs: p.print_help(),
            in_django=in_django,
            log_rather_than_print=log_rather_than_print,
            samizdatmodules=[],
            verbosity=1,
        )
    )
    if not in_django:
        p.add_argument(
            "--quiet",
            "-q",
            help="Be quiet (minimal output)",
            action="store_const",
            const=0,
            dest="verbosity",
        )
        p.add_argument(
            "--verbose",
            "-v",
            help="Be verbose (on stderr).",
            action="store_const",
            const=2,
            dest="verbosity",
        )
    else:
        p.add_argument("-v", "--verbosity", default=1, type=int)
    subparsers = p.add_subparsers(title="commands")

    p_nuke = subparsers.add_parser("nuke", help="Drop all dbsamizdat database objects.")
    p_nuke.set_defaults(func=cmd_nuke)
    add_txdiscipline_argument(p_nuke)
    add_dbarg_argument(p_nuke)

    p_printdot = subparsers.add_parser("printdot", help="Print DB object dependency tree in GraphViz format.")
    p_printdot.set_defaults(func=cmd_printdot)
    perhaps_add_modules_argument(p_printdot)

    p_diff = subparsers.add_parser(
        "diff",
        help="Show differences between dbsamizdat state and database state. Exits nonzero if any are found: 101 when there are excess DB-side objects, 102 if there are excess python-side objects, 103 if both sides have excess objects.",  # noqa: E501
    )
    p_diff.set_defaults(func=cmd_diff)
    add_dbarg_argument(p_diff)
    perhaps_add_modules_argument(p_diff)

    p_refresh = subparsers.add_parser("refresh", help="Refresh materialized views, in dependency order")
    p_refresh.set_defaults(func=cmd_refresh)
    add_txdiscipline_argument(p_refresh)
    add_dbarg_argument(p_refresh)
    perhaps_add_modules_argument(p_refresh)
    p_refresh.add_argument(
        "--belownodes",
        "-b",
        nargs="*",
        help="Limit to views that depend on ENTITYNAMES (usually, specific tables)",
        metavar="ENTITYNAMES",
    )

    p_sync = subparsers.add_parser("sync", help="Make it so!")
    p_sync.set_defaults(func=cmd_sync)
    add_txdiscipline_argument(p_sync)
    add_dbarg_argument(p_sync)
    perhaps_add_modules_argument(p_sync)


def main():
    p = argparse.ArgumentParser(
        description="dbsamizdat, the blissfully naive PostgreSQL database object manager."  # noqa: E501
    )
    augment_argument_parser(p, log_rather_than_print=False)
    args = p.parse_args()
    try:
        args.func(args)
    except SamizdatException as argh:
        exit(f"\n\n\nFATAL: {argh}")
    except KeyboardInterrupt:
        exit("\nInterrupted.")


if __name__ == "__main__":
    main()
