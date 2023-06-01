from dbsamizdat.samizdat import SamizdatView


class AView(SamizdatView):
    sql_template = """
        ${preamble}
        SELECT now();
        ${postamble}
    """
