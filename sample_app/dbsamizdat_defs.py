from dbsamizdat.samizdat import SamizdatView, SamizdatTable


class ExampleTable(SamizdatTable):
    """Example table demonstrating SamizdatTable usage"""

    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """


class AView(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT now();
        ${postamble}
    """


class ViewOnTable(SamizdatView):
    """Example view that depends on the table"""

    deps_on = {ExampleTable}
    sql_template = f"""
        ${{preamble}}
        SELECT name, description
        FROM {ExampleTable.db_object_identity()}
        WHERE created_at > NOW() - INTERVAL '7 days'
        ${{postamble}}
    """
