"""
Shared pytest fixtures for dbsamizdat test suite

This module provides reusable fixtures for:
- Database connections and cleanup
- Test schemas
- Django test environment

Note: Fixtures avoid manual transaction management since get_cursor()
handles transactions automatically.
"""

import os

import pytest
from dotenv import load_dotenv

from dbsamizdat.runner import ArgType, cmd_nuke

load_dotenv()


# ==================== Database Connection ====================


@pytest.fixture(scope="session")
def db_args():
    """
    Database connection arguments.

    Scope: session - created once and reused for all tests.
    Uses DB_URL environment variable or defaults to local PostgreSQL.
    """
    return ArgType(
        txdiscipline="jumbo",
        verbosity=3,
        dburl=os.environ.get("DB_URL", os.environ.get("DBURL", "postgresql://postgres@localhost:5435/postgres")),
    )


# ==================== Database Cleanup ====================


@pytest.fixture
def clean_db(db_args):
    """
    Provide a clean database for each test.

    Scope: function - runs before and after each test.
    Automatically nukes database state before test and cleans up after.

    Usage:
        def test_something(clean_db):
            cmd_sync(clean_db, [MyView])
    """
    cmd_nuke(db_args)
    yield db_args
    cmd_nuke(db_args)


# ==================== Database Cursor ====================


@pytest.fixture
def db_cursor(db_args):
    """
    Provide a database cursor for a single operation.

    Opens its own connection and transaction.
    Use this for simple queries that don't conflict with cmd_sync/cmd_nuke.

    Usage:
        def test_something(db_cursor):
            db_cursor.execute("SELECT ...")
    """
    from dbsamizdat.runner import get_cursor

    with get_cursor(db_args) as cursor:
        yield cursor


# ==================== Test Schemas ====================


@pytest.fixture
def test_schema(db_args):
    """
    Create test_schema and clean up after.

    Uses its own cursor to avoid transaction conflicts.

    Usage:
        def test_custom_schema(clean_db, test_schema):
            class MyTable(SamizdatTable):
                schema = test_schema
    """
    from dbsamizdat.runner import get_cursor

    # Create schema
    with get_cursor(db_args) as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS test_schema")

    yield "test_schema"

    # Cleanup schema
    with get_cursor(db_args) as cursor:
        cursor.execute("DROP SCHEMA IF EXISTS test_schema CASCADE")


# ==================== Sample Data ====================


@pytest.fixture
def fruit_pet_tables(db_args):
    """
    Create Fruit and Pet tables with sample data.

    Uses its own cursor to avoid transaction conflicts.

    Usage:
        def test_view_on_fruit(clean_db, fruit_pet_tables):
            cmd_sync(clean_db, [FruitView])
    """
    from dbsamizdat.runner import get_cursor

    # Create tables
    with get_cursor(db_args) as cursor:
        cursor.execute(
            """
            CREATE TABLE "Fruit" (
                id integer PRIMARY KEY,
                name varchar(100)
            );

            INSERT INTO "Fruit" VALUES
                (1, 'banana'),
                (2, 'pear'),
                (3, 'apple'),
                (4, 'rambutan');

            CREATE TABLE "Pet" (
                id integer PRIMARY KEY,
                name varchar(100)
            );

            INSERT INTO "Pet" VALUES
                (1, 'ocelot'),
                (2, 'khoi carp'),
                (3, 'rolypoly'),
                (4, 'drosophila');
        """
        )

    yield

    # Cleanup
    with get_cursor(db_args) as cursor:
        cursor.execute("DROP TABLE IF EXISTS Fruit, Pet CASCADE")


@pytest.fixture
def refresh_trigger_tables(db_args):
    """
    Create tables d and d2 for refresh trigger tests.

    Uses its own cursor to avoid transaction conflicts.

    Usage:
        def test_sidekicks(clean_db, refresh_trigger_tables):
            # Tables d and d2 already exist
    """
    from dbsamizdat.runner import get_cursor

    # Clean up any existing tables first
    with get_cursor(db_args) as cursor:
        cursor.execute("DROP TABLE IF EXISTS d, d2 CASCADE")

    # Create tables
    with get_cursor(db_args) as cursor:
        cursor.execute("CREATE TABLE d AS SELECT now() AS n")
        cursor.execute("CREATE TABLE d2 AS SELECT now() AS n")

    yield {"d": "d", "d2": "d2"}

    # Cleanup
    with get_cursor(db_args) as cursor:
        cursor.execute("DROP TABLE IF EXISTS d, d2 CASCADE")


# ==================== Django Test Environment ====================


@pytest.fixture(scope="session")
def django_setup():
    """
    Configure minimal Django environment for testing.

    Scope: session - configured once for all Django tests.
    Only runs when Django tests are executed.

    Usage:
        @pytest.mark.django
        def test_queryset(django_setup, clean_db):
            from django.db.models import Model
    """
    try:
        import django
        from django.conf import settings

        if not settings.configured:
            settings.configure(
                DEBUG=True,
                DATABASES={
                    "default": {
                        "ENGINE": "django.db.backends.postgresql",
                        "NAME": "postgres",
                        "USER": "postgres",
                        "PASSWORD": "",
                        "HOST": "localhost",
                        "PORT": "5435",
                    }
                },
                INSTALLED_APPS=[
                    "django.contrib.contenttypes",
                    "dbsamizdat",
                ],
                USE_TZ=True,
            )
            django.setup()
        yield
    except ImportError:
        pytest.skip("Django not installed")


# ==================== Pytest Configuration ====================


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests (no database required)")
    config.addinivalue_line("markers", "integration: Integration tests (require database)")
    config.addinivalue_line("markers", "django: Django integration tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "requires_schema: Tests that need custom schema")
