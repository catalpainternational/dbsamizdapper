"""
Command-line interface for dbsamizdat runner.

This module contains argument parsing and the main entry point:
- augment_argument_parser: Build argument parser
- main: CLI entry point
"""

import argparse
import typing

from ..exceptions import SamizdatException
from .commands import cmd_diff, cmd_nuke, cmd_printdot, cmd_refresh, cmd_sync
from .types import txstyle

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


def augment_argument_parser(p: "ArgumentParser", in_django=False, log_rather_than_print=True):
    """
    Configure argument parser with dbsamizdat commands.

    Args:
        p: ArgumentParser to augment
        in_django: Whether running in Django context
        log_rather_than_print: Use logging vs print statements

    Adds:
        - Global arguments (verbosity, quiet/verbose flags)
        - Subcommands (sync, refresh, nuke, diff, printdot)
        - Database connection arguments (dburl or dbconn)
        - Transaction discipline arguments
    """

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
    """
    Main entry point for dbsamizdat CLI.

    Parses arguments and executes the appropriate command.
    Handles SamizdatException and KeyboardInterrupt gracefully.

    Example:
        $ python -m dbsamizdat.runner sync postgresql:///mydb
        $ python -m dbsamizdat.runner refresh postgresql:///mydb --belownodes users
        $ python -m dbsamizdat.runner nuke postgresql:///mydb
    """
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
