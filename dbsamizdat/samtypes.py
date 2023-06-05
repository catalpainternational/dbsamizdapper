from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Type

from dbsamizdat.exceptions import UnsuitableNameError

PG_IDENTIFIER_MAXLEN = 63
PG_IDENTIFIER_VERBOTEN = set('"')
# Actually allowed, but we'd have to escape it everywhere.
# See https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
# Autogenerated triggers are numbered so as to make them run in samizdat dependency
# order when sorted alphabetically
# (as that's how PostgreSQL determines trigger run order). For this we need to leftpad
# the numbers (because 166 < 23, but 166 > 023, alphabetically)
# Sadly, this poses an artificial limit on the trigger "depth" and an exception will
# be raised if this is exceeded.
# The size here is chosen to retain short-ish trigger names without running into problems
# all too soon.


class entitypes(Enum):
    UNDEFINED = "UNDEFINED"
    TABLE = "TABLE"
    VIEW = "VIEW"
    MATVIEW = "MATERIALIZED VIEW"
    FUNCTION = "FUNCTION"
    TRIGGER = "TRIGGER"


class HasFQ(ABC):
    """
    Ability to "fully qualify" oneself as a postgres instance
    """

    @classmethod
    @abstractmethod
    def fq(cls) -> FQTuple:
        ...


@dataclass(frozen=True)
class FQTuple:
    """
    This dataclass converts different formats of fully qualified names
    to a consistent class format for `DB object identification`
    """

    schema: str | None = "public"
    object_name: str | None = None
    args: str | None = None

    def __lt__(self, other: FQTuple):
        return self.db_object_identity() > other.db_object_identity()

    def db_object_identity(self):
        if self.args is not None:
            return f'"{self.schema}"."{self.object_name}"({self.args})'
        return f'"{self.schema}"."{self.object_name}"'

    @classmethod
    def fqify(cls, arg: FQIffable):
        """
        This is a constructor method
        """
        if isinstance(arg, FQTuple):
            return arg

        elif isinstance(arg, str):
            return cls(schema="public", object_name=arg)

        elif isinstance(arg, tuple):
            """
            Convert a 2tuple of schema, thing_name
            """
            if len(arg) == 1:
                return cls(schema=arg[1])

            if len(arg) == 2:
                return cls(schema=arg[0], object_name=arg[1])

            if len(arg) == 3:
                return cls(schema=arg[0], object_name=arg[1], args=arg[2])

        elif hasattr(arg, "fq"):
            """
            Convert a Samizdat like instance
            """
            return arg.fq()

        else:
            raise TypeError


objectname = str
schemaname = str
sql_query = str


class SqlGeneration(ABC):
    """
    A class which can "sign" itself, "create", and "drop"
    """

    @classmethod
    @abstractmethod
    def sign(cls, cursor: "Mogrifier") -> sql_query:
        """
        Generate COMMENT ON sql storing a signature
        We need the cursor to let psycopg (2) properly escape our json-as-text-string.
        """
        ...

    @classmethod
    @abstractmethod
    def create(cls) -> sql_query:
        """
        SQL to create this DB object
        """
        ...

    @classmethod
    @abstractmethod
    def drop(cls, if_exists: bool) -> sql_query:
        """
        SQL to drop object. Cascade because we have no idea about the dependency tree.
        """
        ...


class HasRefreshTriggers(HasFQ):
    """
    Optional extras for refreshing a view on table changes
    This automatically adds triggers for when a table refreshes to another MatView
    """

    refresh_triggers: set["FQIffable"] = set()

    @classmethod
    def fqrefresh_triggers(cls):
        return {FQTuple.fqify(trigger) for trigger in cls.refresh_triggers}


class HasGetName(ABC):
    """
    This object can return a "Name" for itself and
    will validate that this name is likely to be "nice" for
    postgres to use
    """

    object_name: str | None = None

    @classmethod
    def get_name(cls) -> str:
        return cls.object_name or cls.__name__

    @classmethod
    def validate_name(cls):
        """
        Check whether name is a valid PostgreSQL identifier. Note that we'll quote
        the identifier everywhere ("quoted identifier" per
        https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS)
        """
        name = cls.get_name()
        for char in name:
            if ord(char) > 0x7F:
                raise UnsuitableNameError("Name contains non-ASCII characters", samizdat=cls)
        # Technically we could UESCAPE these,
        # and make the length calculation much more complicated.
        if len(name) > PG_IDENTIFIER_MAXLEN:
            raise UnsuitableNameError("Name is too long", samizdat=cls)
        if badchars := set(name) & PG_IDENTIFIER_VERBOTEN:
            raise UnsuitableNameError(
                f"""Name contains unwelcome characters ({badchars})""",
                samizdat=cls,
            )


class ProtoSamizdat(HasFQ, HasGetName, SqlGeneration):
    """
    A Samizdat class has abilities to create SQL and
    describe itself using a fully qualified name
    """

    deps_on: set[FQIffable] = set()
    deps_on_unmanaged: set[FQIffable] = set()
    schema: schemaname | None = "public"
    sql_template: sql_query | Callable[
        [], sql_query
    ] = """
        -- There should be a class-dependent body for ${samizdatname} here.
        -- See README.md.
        """
    entity_type: entitypes

    @classmethod
    def get_sql_template(cls) -> sql_query:
        return cls.sql_template if isinstance(cls.sql_template, str) else cls.sql_template()

    @classmethod
    def db_object_identity(cls) -> str:
        return cls.fq().db_object_identity()

    @classmethod
    @abstractmethod
    def definition_hash(cls):
        """
        Return the "implanted" hash if preset or generate
        a new descriptive hash of this instance
        """
        ...

    @classmethod
    @abstractmethod
    def fqdeps_on(cls) -> set[FQTuple]:
        ...

    @classmethod
    @abstractmethod
    def fqdeps_on_unmanaged(cls) -> set[FQTuple]:
        ...

    @classmethod
    @abstractmethod
    def dbinfo(cls):
        """
        Returns descriptor (json) for this object, to be stored in the database
        """
        ...

    @classmethod
    @abstractmethod
    def head_id(cls) -> str:
        ...


FQIffable = FQTuple | HasFQ | str | ProtoSamizdat | Type[ProtoSamizdat] | tuple[str, ...]


class HasSidekicks(ABC):
    """
    Some Samizdat classes have additional
    triggers or functions
    One example is Materialized Views with `refresh_triggers`
    """

    @classmethod
    @abstractmethod
    def sidekicks(cls) -> Iterable["ProtoSamizdat"]:
        ...


class Mogrifier(ABC):
    """
    A class which can "mogrify" a SQL string
    This helps to differentiate between psycopg & pscyopg2 'Cursur
    """

    @abstractmethod
    def mogrify(self, *args, **kwargs) -> str | bytes:
        ...

    @property
    def connection(self) -> Any:
        ...


class Cursor(Mogrifier):
    """
    Approximately define what you need in a 'cursor' class
    """

    def execute(self, str) -> None:
        ...

    def close(self) -> None:
        ...

    @abstractmethod
    def fetchall(self) -> list:
        ...
