from dbsamizdat.samtypes import FQIffable, FQTuple


def fqify_node(node: FQIffable) -> FQTuple:
    """
    normalize node names to (schema, nodename) format, assuming the 'public'
    schema for not-fully-qualified node names

    A fully-qualified node has a schema, object name and optionally a 'parameters' part
    """

    if hasattr(node, "fq"):
        return node.fq()  # type: ignore

    elif hasattr(node, "get_name"):
        return FQTuple(schema=node.schema, object_name=node.get_name())  # type: ignore

    elif isinstance(node, str):
        if "." in node:
            firstpart, *rest = node.split(".", maxsplit=1)
            return FQTuple(schema=firstpart, object_name=rest[0])
        return FQTuple(schema="public", object_name=node)
    elif isinstance(node, tuple) and len(node) == 2:
        return FQTuple(schema=node[0], object_name=node[1])
    elif isinstance(node, tuple) and len(node) == 3:
        return FQTuple(schema=node[0], object_name=node[1], args=node[2])

    raise NotImplementedError(f"Invalid fqify_node arg: {node}")
    # Functions have additional parameter to differentiate
    # for type overloads


def nodenamefmt(node) -> str:
    """
    format node for presentation purposes. If it's in the public schema,
    omit the "public" for brevity.
    """
    if isinstance(node, str):
        return node
    if isinstance(node, tuple):
        schema, name, *args = node
        identifier = f"{schema}.{name}" if schema not in {"public", None} else name
        if args and args[0]:
            return f"{identifier}({args[0]})"
        return identifier
    return str(node)  # then it should be a Samizdat


def db_object_identity(thing: FQIffable):
    """
    Convert the "object identity" to a standard "FQTuple"
    and return a string representation of it
    """
    dbid = thing if isinstance(thing, FQTuple) else fqify_node(thing)
    if dbid.args is not None:
        return f'"{dbid.schema}"."{dbid.object_name}"({dbid.args})'
    return f'"{dbid.schema}"."{dbid.object_name}"'


def sqlfmt(sql: str):
    return "\n".join(("\t\t" + line for line in sql.splitlines()))
