"""
Database context management for runner.

This module handles database connections and transaction management:
- get_cursor: Context manager for database cursors
- txi_finalize: Transaction finalization (commit/rollback)
"""

from collections.abc import Generator
from contextlib import contextmanager
from importlib.util import find_spec
from typing import Literal

from ..samtypes import Cursor
from .types import ArgType


@contextmanager
def get_cursor(args: ArgType) -> Generator[Cursor, None, None]:
    """
    Get a database cursor with automatic transaction management.

    This context manager:
    1. Creates appropriate cursor (psycopg/psycopg2/Django)
    2. Begins a transaction
    3. Yields cursor for use
    4. Finalizes transaction based on txdiscipline
    5. Closes cursor

    Args:
        args: ArgType with dburl/dbconn and txdiscipline settings

    Yields:
        Cursor: Database cursor (psycopg2, psycopg3, or Django)

    Raises:
        NotImplementedError: If no valid database driver found

    Example:
        >>> with get_cursor(args) as cursor:
        ...     cursor.execute("SELECT 1")
        ...     result = cursor.fetchone()
    """
    dburl = getattr(args, "dburl", None)

    if args.in_django:
        from django.db import connections

        cursor = connections[args.dbconn].cursor().cursor

    elif dburl and find_spec("psycopg"):
        import psycopg  # noqa: F811

        conn = psycopg.connect(dburl)
        cursor = psycopg.ClientCursor(conn)

    elif dburl and find_spec("psycopg2"):
        import psycopg2

        conn = psycopg2.connect(dburl)
        cursor = conn.cursor()

    else:
        raise NotImplementedError("Required: a Django project or psycopg[2] and a DB url")

    cursor.execute("BEGIN;")
    yield cursor
    txi_finalize(cursor, getattr(args, "txdiscipline", "dryrun"))
    cursor.close()


def txi_finalize(cursor: Cursor, txdiscipline: Literal["jumbo", "dryrun", "checkpoint"]):
    """
    Finalize transaction based on discipline setting.

    Args:
        cursor: Database cursor
        txdiscipline: Transaction discipline
            - "jumbo": COMMIT
            - "checkpoint": COMMIT
            - "dryrun": ROLLBACK

    Raises:
        KeyError: If invalid txdiscipline provided

    Note:
        Both JUMBO and CHECKPOINT commit, but they differ in when
        commits happen during execution (handled by executor).
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
