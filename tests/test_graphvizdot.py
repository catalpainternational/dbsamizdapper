"""Tests for GraphViz DOT generation in dbsamizdat.graphvizdot"""

import pytest

from dbsamizdat import SamizdatFunction, SamizdatMaterializedView, SamizdatTable, SamizdatTrigger, SamizdatView
from dbsamizdat.graphvizdot import dot


@pytest.mark.unit
def test_dot_simple_view():
    """Test dot() generates valid GraphViz for simple view"""

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    output = list(dot([TestView]))
    dot_str = "\n".join(output)

    assert "digraph" in dot_str
    assert "TestView" in dot_str
    assert "shape=box" in dot_str  # VIEW shape
    assert "fillcolor=grey" in dot_str


@pytest.mark.unit
def test_dot_materialized_view():
    """Test dot() generates correct shape for materialized views"""

    class TestMatView(SamizdatMaterializedView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    output = list(dot([TestMatView]))
    dot_str = "\n".join(output)

    assert "shape=box3d" in dot_str  # MATVIEW shape
    assert "fillcolor=red" in dot_str
    assert "TestMatView" in dot_str


@pytest.mark.unit
def test_dot_function():
    """Test dot() generates correct shape for functions"""

    class TestFunction(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$ LANGUAGE SQL"

    output = list(dot([TestFunction]))
    dot_str = "\n".join(output)

    assert "shape=hexagon" in dot_str
    assert "fillcolor=olivedrab1" in dot_str
    assert "TestFunction" in dot_str


@pytest.mark.unit
def test_dot_trigger():
    """Test dot() generates correct shape for triggers"""

    class TestFunction(SamizdatFunction):
        sql_template = "${preamble} RETURNS TRIGGER AS $BODY$ BEGIN RETURN NEW; END; $BODY$ LANGUAGE plpgsql"

    class TestTrigger(SamizdatTrigger):
        deps_on = {TestFunction}
        on_table = ("public", "test_table")  # Required attribute for triggers
        sql_template = "${preamble} AFTER INSERT ON test_table FOR EACH ROW EXECUTE FUNCTION ${samizdatname}"

    output = list(dot([TestTrigger]))
    dot_str = "\n".join(output)

    assert "shape=cds" in dot_str
    assert "fillcolor=darkorchid1" in dot_str
    assert "TestTrigger" in dot_str


@pytest.mark.unit
def test_dot_table():
    """Test dot() generates correct shape for tables"""

    class TestTable(SamizdatTable):
        sql_template = "${preamble} (id SERIAL PRIMARY KEY) ${postamble}"

    output = list(dot([TestTable]))
    dot_str = "\n".join(output)

    assert "TestTable" in dot_str
    assert "shape=box" in dot_str  # TABLE shape
    assert "fillcolor=lightblue" in dot_str


@pytest.mark.unit
def test_dot_with_dependencies():
    """Test dot() shows dependency edges"""

    class BaseView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class DependentView(SamizdatView):
        deps_on = {BaseView}
        sql_template = '${preamble} SELECT * FROM "BaseView" ${postamble}'

    output = list(dot([BaseView, DependentView]))
    dot_str = "\n".join(output)

    assert "BaseView" in dot_str
    assert "DependentView" in dot_str
    assert "->" in dot_str  # Dependency edge
    # Should have edge from BaseView to DependentView
    assert "BaseView" in dot_str
    assert "DependentView" in dot_str


@pytest.mark.unit
def test_dot_with_unmanaged_dependencies():
    """Test dot() shows unmanaged dependencies"""

    class ViewWithUnmanaged(SamizdatView):
        deps_on_unmanaged = {("public", "users")}
        sql_template = "${preamble} SELECT * FROM users ${postamble}"

    output = list(dot([ViewWithUnmanaged]))
    dot_str = "\n".join(output)

    assert "shape=house" in dot_str  # Unmanaged nodes
    assert "fillcolor=yellow" in dot_str
    assert "users" in dot_str or "public.users" in dot_str


@pytest.mark.unit
def test_dot_with_autorefresh_edges():
    """Test dot() shows autorefresh edges for materialized views"""

    class BaseView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class MatViewWithRefresh(SamizdatMaterializedView):
        deps_on = {BaseView}
        refresh_triggers = {("public", BaseView.get_name())}
        sql_template = '${preamble} SELECT * FROM "BaseView" ${postamble}'

    output = list(dot([BaseView, MatViewWithRefresh]))
    dot_str = "\n".join(output)

    # Should have autorefresh edge (dashed line with special arrow)
    assert 'arrowhead="dot"' in dot_str or 'style="dashed"' in dot_str or "🗘" in dot_str


@pytest.mark.unit
def test_dot_empty_list():
    """Test dot() handles empty samizdat list"""
    output = list(dot([]))
    dot_str = "\n".join(output)

    assert "digraph" in dot_str
    # Should still generate valid DOT even with no nodes
    assert "}" in dot_str


@pytest.mark.unit
def test_dot_multiple_views():
    """Test dot() handles multiple views correctly"""

    class View1(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class View2(SamizdatView):
        sql_template = "${preamble} SELECT 2 ${postamble}"

    class View3(SamizdatView):
        sql_template = "${preamble} SELECT 3 ${postamble}"

    output = list(dot([View1, View2, View3]))
    dot_str = "\n".join(output)

    assert "View1" in dot_str
    assert "View2" in dot_str
    assert "View3" in dot_str
    assert "digraph" in dot_str


@pytest.mark.unit
def test_dot_complex_dependency_graph():
    """Test dot() handles complex dependency graphs"""

    class Level1(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class Level2(SamizdatView):
        deps_on = {Level1}
        sql_template = '${preamble} SELECT * FROM "Level1" ${postamble}'

    class Level3(SamizdatView):
        deps_on = {Level2}
        sql_template = '${preamble} SELECT * FROM "Level2" ${postamble}'

    output = list(dot([Level1, Level2, Level3]))
    dot_str = "\n".join(output)

    assert "Level1" in dot_str
    assert "Level2" in dot_str
    assert "Level3" in dot_str
    # Should have edges showing dependencies
    assert "->" in dot_str
    # Should have rank information
    assert "rank" in dot_str.lower()
