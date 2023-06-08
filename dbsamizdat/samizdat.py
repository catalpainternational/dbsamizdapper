from __future__ import annotations

import typing
from collections import Counter
from hashlib import md5
from json import dumps as jsondumps
from string import Template
from time import time as now

from dbsamizdat.samtypes import FQTuple, HasRefreshTriggers, HasSidekicks, Mogrifier, ProtoSamizdat, entitypes

from .util import nodenamefmt

if typing.TYPE_CHECKING:
    try:
        from django.db import connection  # noqa: F401
        from django.db.models import QuerySet
    except ModuleNotFoundError:
        pass

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
        Return the "implanted" hash if preset or generate
        a new descriptive hash of this instance
        """
        if cls.implanted_hash:
            return cls.implanted_hash

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
            dict(
                dbsamizdat=dict(
                    version=_DBINFO_VERSION,
                    created=int(now()),
                    definition_hash=cls.definition_hash(),
                )
            )
        )

    @classmethod
    def sign(cls, cursor):
        """
        Generate COMMENT ON sql storing a signature
        We need the cursor to let psycopg (2) properly escape our json-as-text-string.
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
        subst = dict(
            preamble=f"""CREATE {cls.entity_type.value} {cls.db_object_identity()} AS""",
            postamble="WITH NO DATA" if cls.entity_type.name == "MATVIEW" else "",
            samizdatname=cls.db_object_identity(),
        )
        return Template(cls.get_sql_template()).safe_substitute(subst)

    @classmethod
    def drop(cls, if_exists=False):
        """
        SQL to drop object. Cascade because we have no idea about the dependency tree.
        """
        return f"""DROP {cls.entity_type.value} {"IF EXISTS" if if_exists else ""} {cls.db_object_identity()} CASCADE;"""  # noqa: E501

    @classmethod
    def head_id(cls):
        return hash((cls.schema, cls.get_name(), cls.entity_type.name, cls.definition_hash()))


class SamizdatView(Samizdat):
    entity_type = entitypes.VIEW


class SamizdatFunction(Samizdat):
    entity_type = entitypes.FUNCTION
    function_arguments_signature = ""
    autorefresher = False
    function_name: str | None = None
    # this field serves to identify this node as autogenerated
    # through a materialized view with populated `refresh_triggers` attribute

    @classmethod
    def get_name(cls) -> str:
        return getattr(cls, "function_name") or cls.__name__

    @classmethod
    def fq(cls):
        return FQTuple(
            schema=cls.schema,
            object_name=cls.get_name(),
            args=cls.function_arguments_signature,
        )

    @classmethod
    def creation_identity(cls):
        return '"%s"."%s"(%s)' % (
            cls.schema,
            cls.get_name(),
            cls.creation_function_arguments(),
        )

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
            "|".join([cls.get_sql_template(), cls.db_object_identity(), cls.creation_identity()]).encode("utf-8")
        ).hexdigest()

    @classmethod
    def creation_function_arguments(cls) -> str:
        return getattr(cls, "function_arguments", cls.function_arguments_signature)

    @classmethod
    def create(cls):
        subst = dict(
            preamble=f"CREATE {cls.entity_type.value} {cls.creation_identity()}",
            samizdatname=cls.db_object_identity(),
        )
        return Template(cls.get_sql_template()).safe_substitute(subst)

    @classmethod
    def head_id(cls):
        return hash((cls.schema, cls.get_name(), cls.entity_type.name, cls.definition_hash()))


class SamizdatTrigger(Samizdat):
    entity_type = entitypes.TRIGGER
    on_table: str
    condition: str | None = None
    autorefresher = False
    schema = None

    # autorefresher serves to identify this node as autogenerated
    # through a materialized view with populated `refresh_triggers` attribute

    @classmethod
    def fq(cls):
        """
        A trigger is not directly associated with a schema
        (indirectly it is, through a table.)
        Yet trigger names do not need to be unique in a schema.
        Yet we need a unique identifier for them, within the dbsamizdat collection.
        So we use the table the trigger is attached to as a component
        in the fully qualified name.
        """

        return FQTuple(schema=FQTuple.fqify(cls.on_table).db_object_identity(), object_name=cls.get_name())

    def __str__(self):
        return nodenamefmt(self.fq())

    @classmethod
    def fqdeps_on_unmanaged(cls):
        return {FQTuple.fqify(n) for n in cls.deps_on_unmanaged | {cls.on_table}}

    @classmethod
    def create(cls):
        target_table = FQTuple.fqify(cls.on_table).db_object_identity()
        subst = dict(
            preamble=f"""CREATE {cls.entity_type.value} "{cls.get_name()}" {cls.condition} ON {target_table}""",
            samizdatname=cls.get_name(),
        )
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
                dict(
                    schema=cls.schema,
                    deps_on={cls},
                    autorefresher=True,
                    sql_template="""
                        ${preamble}
                        RETURNS trigger AS $THEBODY$
                        BEGIN
                        %s
                        RETURN NULL;
                        END;
                        $THEBODY$ LANGUAGE plpgsql;
                    """
                    % cls.refresh(),
                ),
            )

    @classmethod
    def gen_refresh_tabletriggers(cls, counter: typing.Counter):
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
                    dict(
                        on_table=triggertable,
                        condition="AFTER UPDATE OR INSERT OR DELETE OR TRUNCATE",
                        deps_on={triggerfn},
                        autorefresher=True,
                        sql_template="""
                                ${preamble}
                                FOR EACH STATEMENT EXECUTE PROCEDURE %s;
                            """
                        % triggerfn.creation_identity(),
                    ),
                )

    @classmethod
    def sidekicks(cls):
        """
        Yields "functions" and "triggers"
        to help manage this Materialized View
        """
        if not cls.refresh_triggers:
            return

        counter: typing.Counter[str] = Counter()
        counter.update({cls.AUTOREFRESHER_COUNTER: 1})
        yield from cls.gen_refresh_triggerfunction()
        yield from cls.gen_refresh_tabletriggers(counter=counter)


class SamizdatMaterializedQuerySet(SamizdatMaterializedView):
    """
    Class to convert a Django queryset into a materialized view
    Primarily this is to simplify deeply nested Django operations
    """

    queryset: QuerySet

    @classmethod
    def _get_query(cls):
        """
        Returns the query, as a string
        """
        try:
            from django.db import connection  # noqa: F811
        except ModuleNotFoundError as E:
            raise ModuleNotFoundError("Django is required for a materialized queryset") from E

        with connection.cursor() as c:
            query = c.mogrify(*cls.queryset.query.sql_with_params())
            if isinstance(query, bytes):
                # Some psycopg2 flavours will give str, others bytes
                # force consistency
                query = query.decode()
        return query

    @classmethod
    def sql_template(cls):
        return f"""${{preamble}} {cls._get_query()} ${{postamble}}"""
