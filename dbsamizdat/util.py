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


def sqlfmt(sql: str):
    return "\n".join(("\t\t" + line for line in sql.splitlines()))
