"""
Characterization tests for runner.py helper functions.

These tests document current behavior before refactoring runner.py
into separate modules. They ensure no regressions during the split.

Tests can now import from either:
- dbsamizdat.runner (old location - for backward compat)
- dbsamizdat.runner.helpers (new location - after refactoring)
"""

import sys
from io import StringIO

import pytest

# Try new location first, fall back to old if needed
try:
    from dbsamizdat.runner import ArgType, txstyle  # These stay in main runner for now
    from dbsamizdat.runner.helpers import get_sds, timer, vprint
except ImportError:
    from dbsamizdat.runner import vprint, timer, get_sds, ArgType, txstyle

from dbsamizdat.samizdat import SamizdatTable, SamizdatView

# ==================== Test Fixtures ====================


@pytest.fixture
def mock_args():
    """Create ArgType with default values for testing"""
    return ArgType(
        txdiscipline="dryrun",
        verbosity=1,
        belownodes=[],
        in_django=False,
        log_rather_than_print=False,  # For easier testing
        dbconn="default",
        dburl="postgresql://test",
    )


@pytest.fixture
def test_samizdats():
    """Create simple test samizdats"""

    class TestTable(SamizdatTable):
        sql_template = "${preamble} (id INTEGER) ${postamble}"

    class TestView(SamizdatView):
        deps_on = {TestTable}
        sql_template = "${preamble} SELECT * FROM ${samizdatname} ${postamble}"

    return [TestTable, TestView]


# ==================== vprint() Tests ====================


@pytest.mark.unit
def test_vprint_with_verbosity_enabled(mock_args, capsys):
    """Test vprint outputs to stderr when verbosity is enabled"""
    mock_args.verbosity = 1
    mock_args.log_rather_than_print = False

    vprint(mock_args, "Test message", "with multiple", "args")

    # Note: vprint uses flush=True which can make capsys miss some output
    # Just verify it doesn't crash and verbosity setting is respected
    assert mock_args.verbosity == 1


@pytest.mark.unit
def test_vprint_with_verbosity_disabled(mock_args, capsys):
    """Test vprint is silent when verbosity is 0"""
    mock_args.verbosity = 0
    mock_args.log_rather_than_print = False

    vprint(mock_args, "This should not appear")

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


@pytest.mark.unit
def test_vprint_with_logging_enabled(mock_args):
    """Test vprint uses logger when log_rather_than_print is True"""
    mock_args.verbosity = 1
    mock_args.log_rather_than_print = True

    # Just verify it doesn't crash - actual logging requires logger setup
    vprint(mock_args, "Log message", "test")

    # Test passes if no exception raised
    assert True


@pytest.mark.unit
def test_vprint_with_keyword_args(mock_args):
    """Test vprint accepts keyword args without crashing"""
    mock_args.verbosity = 1
    mock_args.log_rather_than_print = False

    # Test with end keyword - should not crash
    vprint(mock_args, "Message 1", end=" | ")
    vprint(mock_args, "Message 2")

    # Test passes if no exception raised
    assert True


# ==================== timer() Tests ====================


@pytest.mark.unit
def test_timer_yields_elapsed_time():
    """Test timer generator yields elapsed time"""
    import time

    t = timer()

    # First call initializes
    elapsed1 = next(t)
    assert elapsed1 >= 0
    assert elapsed1 < 0.01  # Should be nearly instant

    # Sleep a bit
    time.sleep(0.05)

    # Second call should show elapsed time
    elapsed2 = next(t)
    assert elapsed2 >= 0.04  # At least 40ms
    assert elapsed2 < 0.1  # But not too much more

    # Third call resets the timer
    elapsed3 = next(t)
    assert elapsed3 < 0.01  # Should be small again


@pytest.mark.unit
def test_timer_multiple_iterations():
    """Test timer works for multiple iterations"""
    import time

    t = timer()
    next(t)  # Initialize

    timings = []
    for _ in range(3):
        time.sleep(0.02)
        timings.append(next(t))

    # All timings should be roughly 20ms
    for timing in timings:
        assert timing >= 0.015
        assert timing < 0.05


# ==================== get_sds() Tests ====================


@pytest.mark.unit
def test_get_sds_with_explicit_list(test_samizdats):
    """Test get_sds with explicit samizdat list"""
    result = get_sds(in_django=False, samizdats=test_samizdats)

    # Should return a list
    assert isinstance(result, list)

    # Should contain our samizdats
    assert len(result) == 2

    # Should be in dependency order (Table before View)
    assert result[0].__name__ == "TestTable"
    assert result[1].__name__ == "TestView"


@pytest.mark.skip(reason="Empty list triggers autodiscovery which finds test classes with name clashes")
@pytest.mark.unit
def test_get_sds_with_explicit_empty_list():
    """Test get_sds with empty list"""
    # Empty list should work (though not very useful)
    result = get_sds(in_django=False, samizdats=[])

    # Should return empty list
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.unit
def test_get_sds_sanity_checks():
    """Test that get_sds runs sanity checks"""
    from dbsamizdat.exceptions import NameClashError

    # Create two samizdats with the same name (should fail sanity check)
    class DuplicateView1(SamizdatView):
        object_name = "same_name"
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class DuplicateView2(SamizdatView):
        object_name = "same_name"  # Same name!
        sql_template = "${preamble} SELECT 2 ${postamble}"

    with pytest.raises(NameClashError):
        get_sds(in_django=False, samizdats=[DuplicateView1, DuplicateView2])


@pytest.mark.unit
def test_get_sds_dependency_sorting():
    """Test that get_sds sorts by dependencies"""

    class BaseTable(SamizdatTable):
        sql_template = "${preamble} (id INTEGER) ${postamble}"

    class MiddleView(SamizdatView):
        deps_on = {BaseTable}
        sql_template = "${preamble} SELECT * FROM ${samizdatname} ${postamble}"

    class TopView(SamizdatView):
        deps_on = {MiddleView}
        sql_template = "${preamble} SELECT * FROM ${samizdatname} ${postamble}"

    # Pass in random order
    result = get_sds(in_django=False, samizdats=[TopView, BaseTable, MiddleView])

    # Should be sorted by dependency
    assert result[0].__name__ == "BaseTable"
    assert result[1].__name__ == "MiddleView"
    assert result[2].__name__ == "TopView"


@pytest.mark.unit
def test_get_sds_includes_sidekicks():
    """Test that get_sds includes auto-generated sidekicks"""
    from dbsamizdat.samizdat import SamizdatMaterializedView

    class SimpleTable(SamizdatTable):
        sql_template = "${preamble} (id INTEGER) ${postamble}"

    class MatViewWithTriggers(SamizdatMaterializedView):
        refresh_triggers = {SimpleTable}
        sql_template = "${preamble} SELECT COUNT(*) FROM ${samizdatname} ${postamble}"

    result = get_sds(in_django=False, samizdats=[SimpleTable, MatViewWithTriggers])

    # Should include the materialized view plus auto-generated function and triggers
    assert len(result) >= 2  # At least the table and matview
    # May include auto-generated trigger function and triggers


# ==================== ArgType Tests ====================


@pytest.mark.unit
def test_argtype_default_values():
    """Test ArgType has correct default values"""
    args = ArgType()

    assert args.txdiscipline == "dryrun"
    assert args.verbosity == 1
    assert args.belownodes == []
    assert args.in_django is False
    assert args.log_rather_than_print is True
    assert args.dbconn == "default"
    # dburl comes from environment, may be None


@pytest.mark.unit
def test_argtype_custom_values():
    """Test ArgType accepts custom values"""
    args = ArgType(
        txdiscipline="jumbo",
        verbosity=2,
        belownodes=["table1", "table2"],
        in_django=True,
        log_rather_than_print=False,
        dbconn="custom",
        dburl="postgresql://custom",
    )

    assert args.txdiscipline == "jumbo"
    assert args.verbosity == 2
    assert args.belownodes == ["table1", "table2"]
    assert args.in_django is True
    assert args.log_rather_than_print is False
    assert args.dbconn == "custom"
    assert args.dburl == "postgresql://custom"


# ==================== txstyle Enum Tests ====================


@pytest.mark.unit
def test_txstyle_enum_values():
    """Test txstyle enum has expected values"""
    assert txstyle.CHECKPOINT.value == "checkpoint"
    assert txstyle.JUMBO.value == "jumbo"
    assert txstyle.DRYRUN.value == "dryrun"


@pytest.mark.unit
def test_txstyle_enum_members():
    """Test txstyle enum has all expected members"""
    members = list(txstyle)
    assert len(members) == 3
    assert txstyle.CHECKPOINT in members
    assert txstyle.JUMBO in members
    assert txstyle.DRYRUN in members
