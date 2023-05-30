from __future__ import annotations

from abc import ABC, ABCMeta
from collections import OrderedDict
from enum import Enum
from hashlib import md5
from json import dumps as jsondumps
from string import Template
from time import time as now
from typing import Type

from .exceptions import UnsuitableNameError
from .util import db_object_identity, fqify_node, nodenamefmt

_DBINFO_VERSION = 1  # Version number for signature format. For future use
PG_IDENTIFIER_MAXLEN = 63
PG_IDENTIFIER_VERBOTEN = set(
    '"'
)  # Actually allowed, but we'd have to escape it everywhere. See https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
# Autogenerated triggers are numbered so as to make them run in samizdat dependency order when sorted alphabetically
# (as that's how PostgreSQL determines trigger run order). For this we need to leftpad the numbers (because 166 < 23, but 166 > 023, alphabetically)
# Sadly, this poses an artificial limit on the trigger "depth" and an exception will be raised if this is exceeded.
# The size here is chosen to retain short-ish trigger names without running into problems all too soon.
TRIGGER_DEPCOUNTER_PADDED_WIDTH = 5


class entitypes(Enum):
    VIEW = "VIEW"
    MATVIEW = "MATERIALIZED VIEW"
    FUNCTION = "FUNCTION"
    TRIGGER = "TRIGGER"


class SamizdatMeta(ABCMeta):
    @property
    def name(cls):
        return cls.__name__

    @property
    def fq(cls):
        return (cls.schema, cls.name)

    @property
    def db_object_identity(cls):
        return db_object_identity(cls.fq)

    def __str__(self):
        funcargs = getattr(self, "function_arguments_signature", None)
        node = (
            (self.schema, self.name, funcargs) if funcargs else (self.schema, self.name)
        )
        return nodenamefmt(node)


class SamizdatFunctionMeta(SamizdatMeta, ABCMeta):
    """
    Since the identity of a functions is its name + some of its arguments (no OUT), in some form (sans defaults, types normalized,...), using the class name as the function name would be inconvenient
    due to class name clashes when defining multiple functions with same name but different arguments.
    Thus we use a separately defined `function_name` attribute.
    """

    @property
    def name(cls):
        return getattr(cls, "function_name", cls.__name__)

    @property
    def fq(cls):
        return (cls.schema, cls.name, cls.function_arguments_signature)

    @property
    def creation_identity(cls):
        return '"%s"."%s"(%s)' % (
            cls.schema,
            cls.name,
            cls.creation_function_arguments(),
        )

    def creation_function_arguments(cls):
        return getattr(cls, "function_arguments", cls.function_arguments_signature)


class SamizdatTriggerMeta(SamizdatMeta, ABCMeta):
    """
    A trigger is not directly associated with a schema (indirectly it is, through a table.)
    Yet trigger names do not need to be unique in a schema.
    Yet we need a unique identifier for them, within the dbsamizdat collection.
    So we use the table the trigger is attached to as a component in the fully qualified name.
    """

    @property
    def fq(cls):
        return (".".join(fqify_node(cls.on_table)), cls.name)

    def __str__(self):
        return nodenamefmt(self.fq)


class Samizdat(ABC):
    """
    Abstract parent class for dbsamizdat classes.
    """

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            """Error: Don't instantiate objects of type "%s".\nUse it as a static class."""
            % self.__class__.__name__
        )

    deps_on: set[str | tuple[str, str] | tuple[str, str, str] | Samizdat | Type[Samizdat]] = set()
    deps_on_unmanaged: set[str | tuple[str, str] | tuple[str, str, str] | Samizdat] = set()
    schema: str | None = "public"
    sql_template = """
        -- There should be a class-dependent body for ${samizdatname} here.
        -- See README.md.
        """

    @classmethod
    def validate_name(cls):
        """
        Check whether name is a valid PostgreSQL identifier. Note that we'll quote the identifier everywhere ("quoted identifier" per https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS)
        """
        if any(map(lambda c: ord(c) > 0x7F, cls.name)):
            raise UnsuitableNameError(
                "Name contains non-ASCII characters", samizdat=cls
            )  # Technically we could UESCAPE these, and make the length calculation much more complicated.
        if len(cls.name) > PG_IDENTIFIER_MAXLEN:
            raise UnsuitableNameError("Name is too long", samizdat=cls)
        if set(cls.name) & PG_IDENTIFIER_VERBOTEN:
            raise UnsuitableNameError(
                f"""Name contains unwelcome characters ({set(cls.name) & PG_IDENTIFIER_VERBOTEN})""",
                samizdat=cls,
            )

    @classmethod
    def definition_hash(cls):
        try:
            return cls.implanted_hash  # if this thing has been read from the DB
        except AttributeError:
            use_attrs = ("sql_template", "db_object_identity", "creation_identity")
            return md5(
                "|".join(
                    map(lambda attrname: getattr(cls, attrname, ""), use_attrs)
                ).encode("utf-8")
            ).hexdigest()

    @classmethod
    def fqify(cls, ref):
        if isinstance(ref, str):
            return (cls.schema, ref)
        if isinstance(ref, SamizdatMeta):
            return ref.fq
        if isinstance(ref, tuple):
            return ref
        raise ValueError("Not a string, tuple, or Samizdat: '%s'" % ref)

    @classmethod
    def fqdeps_on(cls):
        return set(map(cls.fqify, cls.deps_on))

    @classmethod
    def fqdeps_on_unmanaged(cls):
        return set(map(cls.fqify, cls.deps_on_unmanaged))

    @classmethod
    def dbinfo(cls):
        """
        Returns descriptor (json) for this object, to be stored in the database
        """
        samizdat_dbinfo = OrderedDict()
        samizdat_dbinfo_contents = OrderedDict()
        samizdat_dbinfo_contents["version"] = _DBINFO_VERSION
        samizdat_dbinfo_contents["created"] = int(now())
        samizdat_dbinfo_contents["definition_hash"] = cls.definition_hash()
        samizdat_dbinfo["dbsamizdat"] = samizdat_dbinfo_contents
        return jsondumps(samizdat_dbinfo)

    @classmethod
    def sign(cls, cursor):
        """
        Generate COMMENT ON sql storing a signature
        We need the cursor to let psycopg (2) properly escape our json-as-text-string.
        """
        return cursor.mogrify(
            """COMMENT ON {cls.entity_type.value} {cls.db_object_identity} IS %s;""".format(
                cls=cls
            ),
            (cls.dbinfo(),),
        ).decode()

    @classmethod
    def create(cls):
        """
        SQL to create this DB object
        """
        subst = dict(
            preamble="""CREATE {cls.entity_type.value} {cls.db_object_identity} AS""".format(
                cls=cls
            ),
            postamble={"MATVIEW": "WITH NO DATA"}.get(cls.entity_type.name, ""),
            samizdatname=cls.db_object_identity,
        )
        return Template(cls.sql_template).safe_substitute(subst)

    @classmethod
    def drop(cls, if_exists=False):
        """
        SQL to drop object. Cascade because we have no idea about the dependency tree.
        """
        return "DROP {cls.entity_type.value} {if_exists} {cls.db_object_identity} CASCADE;".format(
            cls=cls, if_exists={True: "IF EXISTS"}.get(if_exists, "")
        )

    @classmethod
    def and_sidekicks(cls, counter=None):
        """
        On some classes, this will yield autogenerated sidekick classes
        """
        yield cls
        yield from ()

    @classmethod
    def head_id(cls):
        return hash((cls.schema, cls.name, cls.entity_type.name, cls.definition_hash()))


class SamizdatView(Samizdat, ABC, metaclass=SamizdatMeta):
    entity_type = entitypes.VIEW


class SamizdatFunction(Samizdat, ABC, metaclass=SamizdatFunctionMeta):
    entity_type = entitypes.FUNCTION
    function_arguments_signature = ""
    autorefresher = False  # this field serves to identify this node as autogenerated through a materialized view with populated `refresh_triggers` attribute

    @classmethod
    def create(cls):
        subst = dict(
            preamble="""CREATE {cls.entity_type.value} {cls.creation_identity}""".format(
                cls=cls
            ),
            samizdatname=cls.db_object_identity,
        )
        return Template(cls.sql_template).safe_substitute(subst)

    @classmethod
    def head_id(cls):
        return hash((cls.schema, cls.name, cls.entity_type.name, cls.definition_hash()))


class SamizdatTrigger(Samizdat, ABC, metaclass=SamizdatTriggerMeta):
    schema: str | None = None  # Triggers are only indirectly in a schema (through the table they're defined on.)
    entity_type = entitypes.TRIGGER
    on_table: str | None = None
    condition: str | None = None
    autorefresher = False  # this field serves to identify this node as autogenerated through a materialized view with populated `refresh_triggers` attribute

    @classmethod
    def fqdeps_on_unmanaged(cls):
        return {fqify_node(n) for n in cls.deps_on_unmanaged | {cls.on_table}}

    @classmethod
    def create(cls):
        subst = dict(
            preamble="""CREATE {cls.entity_type.value} "{cls.name}" {cls.condition} ON {target_table}""".format(
                cls=cls, target_table=db_object_identity(cls.on_table)
            ),
            samizdatname=cls.name,
        )
        return Template(cls.sql_template).safe_substitute(subst)

    @classmethod
    def drop(cls, if_exists=False):
        return "DROP {cls.entity_type.value} {if_exists} {cls.name} ON {target_table} CASCADE;".format(
            cls=cls,
            if_exists={True: "IF EXISTS"}.get(if_exists, ""),
            target_table=db_object_identity(cls.on_table),
        )

    @classmethod
    def sign(cls, cursor):
        return cursor.mogrify(
            """COMMENT ON {cls.entity_type.value} "{cls.name}" ON {on_table} IS %s;""".format(
                cls=cls, on_table=db_object_identity(cls.on_table)
            ),
            (cls.dbinfo(),),
        ).decode()

    @classmethod
    def head_id(cls):
        return hash(
            (
                fqify_node(cls.on_table)[0],
                cls.name,
                cls.entity_type.name,
                fqify_node(cls.on_table)[1],
                cls.definition_hash(),
            )
        )


class SamizdatMaterializedView(Samizdat, ABC, metaclass=SamizdatMeta):
    entity_type = entitypes.MATVIEW
    refresh_concurrently = False
    refresh_triggers: set[Samizdat | tuple[str, str]] = set()
    AUTOREFRESHER_COUNTER = "autorefresher"

    @classmethod
    def fqrefresh_triggers(cls):
        return set(map(cls.fqify, cls.refresh_triggers))

    @classmethod
    def refresh(cls, concurrent_allowed=True):
        return """REFRESH MATERIALIZED VIEW {concurrently} {cls.db_object_identity};""".format(
            cls=cls,
            concurrently={True: "CONCURRENTLY"}.get(
                concurrent_allowed and cls.refresh_concurrently, ""
            ),
        )

    @classmethod
    def gen_refresh_triggerfunction(cls):
        """
        yields a SamizdatFunction; a trigger-returning function that refreshes this materialized view.
        """
        if cls.refresh_triggers:
            yield type(
                f"{cls.name}_refresh",
                (SamizdatFunction,),
                dict(
                    schema=cls.schema,  # The trigger function will be created in the same schema as the view. That's not a requirement, but we have to choose *something*.
                    deps_on={cls.fq},
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
    def gen_refresh_tabletriggers(cls, counter=None):
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
            for ix, triggertable in enumerate(sorted(cls.fqrefresh_triggers())):
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
                        deps_on={triggerfn.fq},
                        autorefresher=True,
                        sql_template="""
                                ${preamble}
                                FOR EACH STATEMENT EXECUTE PROCEDURE %s;
                            """
                        % db_object_identity(triggerfn.fq),
                    ),
                )

    @classmethod
    def and_sidekicks(cls, counter=None):
        yield cls
        if cls.refresh_triggers:
            counter.update({cls.AUTOREFRESHER_COUNTER: 1})
            yield from cls.gen_refresh_triggerfunction()
            yield from cls.gen_refresh_tabletriggers(counter=counter)
