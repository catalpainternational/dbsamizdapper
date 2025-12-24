from __future__ import annotations

from collections import Counter
from hashlib import md5
from json import dumps as jsondumps
from string import Template
from time import time as now
from typing import TYPE_CHECKING, Any, TypeGuard

from dbsamizdat.samtypes import (
    FQIffable,
    FQTuple,
    HasRefreshTriggers,
    HasSidekicks,
    Mogrifier,
    ProtoSamizdat,
    entitypes,
    sql_query,
)

from .util import nodenamefmt

if TYPE_CHECKING:
    import contextlib
    from collections.abc import Iterable

    with contextlib.suppress(ModuleNotFoundError, ImportError):
        from django.db.models import Model, QuerySet

_DBINFO_VERSION = 1  # Version number for signature format. For future use

TRIGGER_DEPCOUNTER_PADDED_WIDTH = 5


class Samizdat(ProtoSamizdat):
    """
    Abstract parent class for dbsamizdat classes.
    """

    entity_type: entitypes = entitypes.VIEW
    # This is populated when restoring the class info from the database
    implanted_hash: str | None = None

    @classmethod
    def db_object_identity(cls):
        return cls.fq().db_object_identity()

    @classmethod
    def fq(cls):
        return FQTuple(schema=cls.schema, object_name=cls.get_name())

    def __str__(self):
        funcargs = getattr(self, "function_arguments_signature", None)
        node = (self.schema, self.get_name(), funcargs) if funcargs else (self.schema, self.get_name())
        return nodenamefmt(node)

    @classmethod
    def definition_hash(cls):
        """
        Return the "implanted" hash if preset or generate a new descriptive hash.

        Reconstructed classes from the database will have implanted_hash set.
        For regular classes, computes hash from sql_template and db_object_identity.
        """
        implanted = getattr(cls, "implanted_hash", None)

        # Valid implanted_hash must be non-empty and not the string "None"
        if implanted and implanted not in ("", "None"):
            return implanted

        # Compute hash from template and identity
        return md5("|".join([cls.get_sql_template(), cls.db_object_identity()]).encode("utf-8")).hexdigest()

    @classmethod
    def fqdeps_on(cls):
        return {FQTuple.fqify(dep) for dep in cls.deps_on}

    @classmethod
    def fqdeps_on_unmanaged(cls):
        return {FQTuple.fqify(dep) for dep in cls.deps_on_unmanaged}

    @classmethod
    def dbinfo(cls):
        """
        Returns descriptor (json) for this object, to be stored in the database
        """
        return jsondumps(
            {
                "dbsamizdat": {
                    "version": _DBINFO_VERSION,
                    "created": int(now()),
                    "definition_hash": cls.definition_hash(),
                }
            }
        )

    @classmethod
    def sign(cls, cursor):
        """
        Generate COMMENT ON sql storing a signature
        We need the cursor to let psycopg (2) properly escape our json-as-text-string.
        
        Note: For Option A functions with parameters, if signing fails due to
        incorrect signature, the executor will query the database to find the
        actual signature and raise FunctionSignatureError with candidate arguments.
        """
        comment = cursor.mogrify(
            f"""COMMENT ON {cls.entity_type.value} {cls.db_object_identity()} IS %s;""",
            (cls.dbinfo(),),
        )
        if isinstance(comment, bytes):
            return comment.decode()
        return comment

    @classmethod
    def create(cls):
        """
        SQL to create this DB object
        """
        _AS = "" if cls.entity_type.name == "TABLE" else " AS "
        opts = ["UNLOGGED "] if getattr(cls, "unlogged", False) else []
        subst = {
            "preamble": f"""CREATE {" ".join(opts)}{cls.entity_type.value} {cls.db_object_identity()}{_AS}""",
            "postamble": "WITH NO DATA" if sd_is_matview(cls) else "",
            "samizdatname": cls.db_object_identity(),
        }
        return Template(cls.get_sql_template()).safe_substitute(subst)

    @classmethod
    def drop(cls, if_exists=False):
        """
        SQL to drop object. Cascade because we have no idea about the dependency tree.
        """
        return (
            f"""DROP {cls.entity_type.value} {"IF EXISTS" if if_exists else ""} {cls.db_object_identity()} CASCADE;"""  # noqa: E501
        )

    @classmethod
    def head_id(cls):
        return hash((cls.schema, cls.get_name(), cls.entity_type.name, cls.definition_hash()))


class SamizdatView(Samizdat):
    entity_type = entitypes.VIEW


class SamizdatTable(Samizdat):
    entity_type = entitypes.TABLE
    unlogged = False  # By default, tables are logged (durable)


class SamizdatFunction(Samizdat):
    """Base class for defining PostgreSQL functions.

    There are two approaches for defining functions:

    **Option A: Full CREATE FUNCTION in template**
        Include the complete `CREATE FUNCTION` statement in your `sql_template`
        and set `function_arguments_signature = ""`.

    **Option B: Use `${preamble}` (Recommended)**
        Omit `CREATE FUNCTION` from your `sql_template` and use `${preamble}`,
        which automatically includes `CREATE FUNCTION {schema}.{name}({signature})`.
        Set `function_arguments_signature` to your parameter signature
        (e.g., `"name TEXT, id INT"`).

    Attributes:
        function_arguments_signature: Parameter signature without parentheses.
            Defaults to `""` (no parameters). Example: `"name TEXT, age INTEGER"`.
        function_name: Override the function name. Defaults to the class name.
            Useful for function polymorphism (multiple functions with same name,
            different signatures).
        function_arguments: Full function arguments including defaults, IN/OUT/INOUT,
            etc. Only needed when call signature differs from full arguments.
        autorefresher: Flag indicating if this function is auto-generated for
            materialized view refresh triggers.

    Important:
        - `creation_identity()` always includes parentheses: `"schema"."name"({args})`
        - Even when `function_arguments_signature = ""`, it becomes `"schema"."name"()`
        - Do not include `CREATE FUNCTION` in your template when using `${preamble}`
          as this causes signature duplication errors.

    For detailed examples and common pitfalls, see USAGE.md.

    Example:
        >>> class MyFunction(SamizdatFunction):
        ...     function_arguments_signature = "name TEXT"
        ...     sql_template = '''
        ...         ${preamble}
        ...         RETURNS TEXT AS
        ...         $BODY$
        ...         SELECT UPPER(name);
        ...         $BODY$
        ...         LANGUAGE SQL;
        ...     '''
    """

    entity_type = entitypes.FUNCTION
    function_arguments_signature = ""
    autorefresher = False
    function_name: str | None = None
    # this field serves to identify this node as autogenerated
    # through a materialized view with populated `refresh_triggers` attribute

    @classmethod
    def get_name(cls) -> str:
        return cls.function_name or cls.__name__

    @classmethod
    def fq(cls):
        return FQTuple(
            schema=cls.schema,
            object_name=cls.get_name(),
            args=cls.function_arguments_signature,
        )

    @classmethod
    def creation_identity(cls):
        return f'"{cls.schema}"."{cls.get_name()}"({cls.creation_function_arguments()})'

    @classmethod
    def definition_hash(cls):
        """
        Return the "implanted" hash if preset or generate
        a new descriptive hash of this instance
        """
        if cls.implanted_hash:
            return cls.implanted_hash

        # "Functions" adapt the hash to include creation options
        return md5(
            "|".join(
                [
                    cls.get_sql_template(),
                    cls.db_object_identity(),
                    cls.creation_identity(),
                ]
            ).encode("utf-8")
        ).hexdigest()

    @classmethod
    def creation_function_arguments(cls) -> str:
        return getattr(cls, "function_arguments", cls.function_arguments_signature)

    @classmethod
    def create(cls):
        subst = {
            "preamble": f"CREATE {cls.entity_type.value} {cls.creation_identity()}",
            "samizdatname": cls.db_object_identity(),
        }
        return Template(cls.get_sql_template()).safe_substitute(subst)

    @classmethod
    def head_id(cls):
        return hash((cls.schema, cls.get_name(), cls.entity_type.name, cls.definition_hash()))


class SamizdatTrigger(Samizdat):
    """
    Database trigger samizdat.

    Note: Triggers don't have their own schema; they belong to tables.
    The schema attribute is derived from the table at runtime via fq().
    This fixes the previous LSP violation where schema was set to None.
    """

    entity_type = entitypes.TRIGGER
    on_table: str | FQIffable
    condition: str | None = None
    autorefresher = False
    # schema inherited from Samizdat (defaults to "public")
    # The actual schema used is derived from on_table in fq()

    # autorefresher serves to identify this node as autogenerated
    # through a materialized view with populated `refresh_triggers` attribute

    @classmethod
    def fq(cls):
        """
        Get fully qualified name for trigger.

        Triggers in PostgreSQL are uniquely identified by (trigger_name, table).
        We encode this by using the table's schema and composing a unique object name
        that includes both the trigger name and table reference.

        This maintains backward compatibility while fixing the LSP violation
        where we previously misused the schema field to store the full table identity.
        """
        table_fq = FQTuple.fqify(cls.on_table)

        # Use the table's schema (proper LSP compliance)
        # Compose a unique name that includes table reference
        return FQTuple(
            schema=table_fq.schema,
            object_name=f"{cls.get_name()}__on__{table_fq.object_name}",
        )

    def __str__(self):
        return nodenamefmt(self.fq())

    @classmethod
    def fqdeps_on_unmanaged(cls):
        return {FQTuple.fqify(n) for n in cls.deps_on_unmanaged | {cls.on_table}}

    @classmethod
    def create(cls):
        target_table = FQTuple.fqify(cls.on_table).db_object_identity()
        subst = {
            "preamble": f"""CREATE {cls.entity_type.value} "{cls.get_name()}" {cls.condition} ON {target_table}""",
            "samizdatname": cls.get_name(),
        }
        return Template(cls.get_sql_template()).safe_substitute(subst)

    @classmethod
    def drop(cls, if_exists=False):
        ident = FQTuple.fqify(cls.on_table).db_object_identity()
        return (
            f"""DROP {cls.entity_type.value} {"IF EXISTS" if if_exists else ""} {cls.get_name()} ON {ident} CASCADE;"""
        )

    @classmethod
    def sign(cls, cursor: Mogrifier):
        comment = cursor.mogrify(
            f"""COMMENT ON {cls.entity_type.value} "{cls.get_name()}" ON {FQTuple.fqify(cls.on_table).db_object_identity()} IS %s;""",
            (cls.dbinfo(),),
        )
        if isinstance(comment, bytes):
            return comment.decode()
        return comment

    @classmethod
    def head_id(cls):
        return hash(
            (
                FQTuple.fqify(cls.on_table).schema,
                cls.get_name(),
                cls.entity_type.name,
                FQTuple.fqify(cls.on_table).object_name,
                cls.definition_hash(),
            )
        )


class SamizdatWithSidekicks(Samizdat, HasSidekicks, HasRefreshTriggers):
    """
    This class is here for mypy detection of sidekicks function
    """

    pass


class SamizdatMaterializedView(SamizdatWithSidekicks):
    entity_type = entitypes.MATVIEW
    refresh_concurrently = False
    refresh_triggers = set()
    AUTOREFRESHER_COUNTER = "autorefresher"

    @classmethod
    def refresh(cls, concurrent_allowed=True):
        concurrently = "CONCURRENTLY" if (concurrent_allowed and cls.refresh_concurrently) else ""
        return f"""REFRESH MATERIALIZED VIEW {concurrently} {cls.db_object_identity()};"""

    @classmethod
    def gen_refresh_triggerfunction(cls):
        """
        yields a SamizdatFunction; a trigger-returning function that refreshes
        this materialized view.
        The trigger function will be created in the same schema as the view.
        That's not a requirement, but we have to choose *something*.
        """
        if cls.refresh_triggers:
            yield type(
                f"{cls.get_name()}_refresh",
                (SamizdatFunction,),
                {
                    "schema": cls.schema,
                    "deps_on": {cls},
                    "autorefresher": True,
                    "sql_template": f"""
                        ${{preamble}}
                        RETURNS trigger AS $THEBODY$
                        BEGIN
                        {cls.refresh()}
                        RETURN NULL;
                        END;
                        $THEBODY$ LANGUAGE plpgsql;
                    """,
                },
            )

    @classmethod
    def gen_refresh_tabletriggers(cls, counter: Counter):
        """
        yields SamizdatTriggers on the tables, triggering a refresh this materialized view
        """
        dep_order = counter[cls.AUTOREFRESHER_COUNTER]
        if dep_order > 10**TRIGGER_DEPCOUNTER_PADDED_WIDTH - 1:
            raise ValueError(
                f"Trigger creation order {dep_order} requires a autonumbering padding width increase (TRIGGER_DEPCOUNTER_PADDED_WIDTH)."
            )
        triggerfn = next(cls.gen_refresh_triggerfunction(), None)
        if triggerfn:
            for ix, triggertable in enumerate(cls.fqrefresh_triggers()):
                class_name = f"t%.{TRIGGER_DEPCOUNTER_PADDED_WIDTH}d_%d_autorefresh" % (
                    dep_order,
                    ix,
                )
                yield type(
                    class_name,
                    (SamizdatTrigger,),
                    {
                        "on_table": triggertable,
                        "condition": "AFTER UPDATE OR INSERT OR DELETE OR TRUNCATE",
                        "deps_on": {triggerfn},
                        "autorefresher": True,
                        "sql_template": f"""
                                ${{preamble}}
                                FOR EACH STATEMENT EXECUTE PROCEDURE {triggerfn.creation_identity()};
                            """,
                    },
                )

    @classmethod
    def sidekicks(cls) -> Iterable[SamizdatFunction | SamizdatTrigger]:
        """
        Yields "functions" and "triggers"
        to help manage this Materialized View
        """
        if not cls.refresh_triggers:
            return

        counter: Counter[str] = Counter()
        counter.update({cls.AUTOREFRESHER_COUNTER: 1})
        yield from cls.gen_refresh_triggerfunction()
        yield from cls.gen_refresh_tabletriggers(counter=counter)


class SamizdatQuerySet(Samizdat):
    """
    Class to convert a Django queryset into a materialized view
    Primarily this is to simplify deeply nested Django operations
    """

    queryset: QuerySet

    @classmethod
    def get_queryset(cls):
        return cls.queryset

    @classmethod
    def sql_template(cls):
        return f"""${{preamble}} {cls.get_query(cls.get_queryset())} ${{postamble}}"""

    @classmethod
    def get_query(cls, queryset: QuerySet) -> sql_query:
        """
        Returns the query, as a string
        """
        from django.db import connection  # noqa: F811

        with connection.cursor() as c:
            query = c.mogrify(*queryset.query.sql_with_params())
            if isinstance(query, bytes):
                # Some psycopg2 flavours will give str, others bytes
                # force consistency
                query = query.decode()
        return query


class SamizdatMaterializedQuerySet(SamizdatQuerySet, SamizdatMaterializedView):
    entity_type = entitypes.MATVIEW


class SamizdatModel(SamizdatQuerySet):
    """
    This is an abstraction around relating a Django unmanaged model
    to a Materialized View, defined as a Django 'query' instance.

    The class takes two parameters: a "model" instance
    and a "queryset".

    The fields returned
    """

    model: Model

    @classmethod
    def _add_id(cls, queryset: QuerySet):
        """
        Auto add an "id" column;
        this is required for Django's admin to
        function correctly as it uses the primary key
        to add a detail view
        """
        from django.db.models.expressions import Window
        from django.db.models.functions import RowNumber

        return queryset.annotate(id=Window(expression=RowNumber()))

    @classmethod
    def get_queryset(cls):
        """
        Get the 'values' associted with the fields defined on the model
        """
        fields = [field.attname for field in cls.model._meta.get_fields()]
        return cls._add_id(cls.queryset).values(*fields)

    @classmethod
    def get_name(cls):
        """
        Use the name as Django defined it
        """
        return cls.model._meta.db_table


class SamizdatMaterializedModel(SamizdatModel, SamizdatMaterializedView):
    entity_type = entitypes.MATVIEW


def sd_is_view(sd: Any) -> TypeGuard[SamizdatView]:
    return getattr(sd, "entity_type", None) == entitypes.VIEW


def sd_is_matview(sd: Any) -> TypeGuard[SamizdatMaterializedView]:
    """
    This is used to determine refresh methods when sync'ing
    """
    return getattr(sd, "entity_type", None) == entitypes.MATVIEW


def sd_is_function(sd: Any) -> TypeGuard[SamizdatFunction]:
    return getattr(sd, "entity_type", None) == entitypes.FUNCTION


def sd_is_trigger(sd: Any) -> TypeGuard[SamizdatTrigger]:
    return getattr(sd, "entity_type", None) == entitypes.TRIGGER
