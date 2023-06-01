import warnings
from enum import IntFlag
from json import loads as jsonloads
from typing import Iterable, NamedTuple, Type

from dbsamizdat.samizdat import Samizdat

from . import SamizdatFunction, SamizdatMaterializedView, SamizdatTrigger, SamizdatView
from .samtypes import Cursor, ProtoSamizdat, entitypes

COMMENT_MAGIC = """{"dbsamizdat": {"version":"""


class DBObjectType(IntFlag):
    SAMIZDAT = 1
    FOREIGN = 2


name = str
hash_ = str


class StateTuple(NamedTuple):
    schemaname: str
    viewname: str
    objecttype: str
    commentcontent: str
    args: str | None
    definition_hash: str | None


def get_dbstate(
    cursor: "Cursor",
) -> Iterable[StateTuple]:
    """
    Capture and annotate the current DB state (functions, views and triggers)
    Identifies DBSamizdat managed objects based on their "comment".
    Returns the schema; function / view / object name; "type"; and
    comment embedded in the hash
    "Functions" also include parameters
    """

    function_filter = "p.prokind NOT IN ('a', 'w', 'p')"

    fetches = {
        entitypes.VIEW: """
            SELECT n.nspname AS schemaname,
                c.relname AS viewname,
                'VIEW' as objecttype,
                pg_catalog.obj_description(c.oid, 'pg_class') AS commentcontent,
                NULL as args,
                NULL as definition_hash
            FROM pg_catalog.pg_class c
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'v'
                AND n.nspname <> 'pg_catalog'
                AND n.nspname <> 'information_schema'
                AND n.nspname !~ '^pg_toast'
            """,
        entitypes.MATVIEW: """
            SELECT n.nspname,
                c.relname,
                'MATVIEW',
                pg_catalog.obj_description(c.oid, 'pg_class') AS commentcontent,
                NULL as args,
                NULL as definition_hash
            FROM pg_catalog.pg_class c
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'm'
                AND n.nspname <> 'pg_catalog'
                AND n.nspname <> 'information_schema'
                AND n.nspname !~ '^pg_toast'
            """,
        entitypes.FUNCTION: f"""
            SELECT n.nspname,
                p.proname,
                'FUNCTION',
                pg_catalog.obj_description(p.oid, 'pg_proc'),
                pg_catalog.pg_get_function_identity_arguments(p.oid) AS args,
                NULL as definition_hash
            FROM pg_catalog.pg_proc p
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE {function_filter}
                AND n.nspname <> 'pg_catalog'
                AND n.nspname <> 'information_schema'
            """,
        entitypes.TRIGGER: """
            SELECT
                pn.nspname,
                pt.tgname,
                'TRIGGER',
                pg_catalog.obj_description(pt.oid, 'pg_trigger') AS commentcontent,
                pc.relname,
                NULL as definition_hash
            FROM
                pg_trigger pt
                LEFT JOIN pg_class pc ON pt.tgrelid = pc.oid
                LEFT JOIN pg_catalog.pg_namespace pn ON pn.oid = pc.relnamespace
            WHERE
                pt.tgisinternal = False
            """,
    }

    for fetch_query in fetches.values():
        cursor.execute(fetch_query)
        items = (StateTuple(*c) for c in cursor.fetchall())
        # Comment is the last item in the query
        for item in items:
            if not (item.commentcontent and item.commentcontent.startswith(COMMENT_MAGIC)):
                continue
            try:
                meta = jsonloads(item.commentcontent)["dbsamizdat"]
                # This is probably? a DBSamizdat
                # Get the hash value from the comment
                hashattr = "sql_template_hash" if meta["version"] == 0 else "definition_hash"
                yield item._replace(definition_hash=meta[hashattr])
            except Exception as E:
                warnings.warn(f"{E}")
                continue


def dbinfo_to_class(info: StateTuple) -> type[Samizdat]:
    """
    Reconstruct a class out of information found in the DB
    """
    typemap = {
        c.entity_type: c
        for c in (
            SamizdatView,
            SamizdatMaterializedView,
            SamizdatFunction,
            SamizdatTrigger,
        )
    }

    entity_type = entitypes[info.objecttype]
    classfields: dict[str, None | str | tuple[str, str]] = dict(
        schema=info.schemaname,
        implanted_hash=str(info.definition_hash),
    )
    if entity_type == entitypes.FUNCTION:
        classfields.update(
            dict(
                function_arguments_signature=str(info.args),
                function_name=info.viewname,
            )
        )
    elif entity_type == entitypes.TRIGGER:
        table = str(info.args)
        classfields.update(
            dict(
                schema=None,
                on_table=(info.schemaname, table),
            )
        )
    klass: type[Samizdat] = type(info.viewname, (typemap[entitypes[info.objecttype]],), classfields)
    return klass


class DBComparison(NamedTuple):
    issame: bool
    excess_dbstate: Iterable[Type[ProtoSamizdat]]
    excess_definedstate: Iterable[Samizdat]


def dbstate_equals_definedstate(cursor: Cursor, samizdats: Iterable[Samizdat]):
    """
    Returns whether there are id's to add or remove and if so which
    samizdat classes (by id) need to be added or removed to sync database
    """

    current_state = get_dbstate(cursor)
    state_to_classes = (dbinfo_to_class(s) for s in current_state)

    dbstate = {ds.head_id(): ds for ds in state_to_classes}
    definedstate = {ds.head_id(): ds for ds in samizdats}

    db_keys = dbstate.keys()
    defined_keys = definedstate.keys()

    return DBComparison(
        issame=db_keys == defined_keys,
        excess_dbstate={dbstate[k] for k in db_keys - defined_keys},
        excess_definedstate={definedstate[k] for k in defined_keys - db_keys},
    )
