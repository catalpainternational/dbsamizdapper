# Test Coverage Improvement Plan

Current Coverage: **56.75%** | Target: **70%+**

## Priority 1: High-Impact, Easy Wins (Can reach ~65%)

### 1. Library API Functions (`dbsamizdat/api.py` - 0% coverage)

**Impact**: High - These are the main entry points for users
**Effort**: Low - Can be tested with mocks

**Tests Needed**:
```python
# tests/test_api.py
@pytest.mark.unit
def test_sync_with_module_names():
    """Test sync() function with samizdatmodules parameter"""
    from unittest.mock import patch, MagicMock
    from dbsamizdat import sync

    with patch('dbsamizdat.api._cmd_sync') as mock_sync:
        sync("postgresql:///test", samizdatmodules=["myapp.views"])
        mock_sync.assert_called_once()
        args = mock_sync.call_args[0][0]
        assert args.samizdatmodules == ["myapp.views"]

@pytest.mark.unit
def test_refresh_with_belownodes():
    """Test refresh() with belownodes filter"""
    from unittest.mock import patch
    from dbsamizdat import refresh

    with patch('dbsamizdat.api._cmd_refresh') as mock_refresh:
        refresh("postgresql:///test", belownodes=["users"])
        args = mock_refresh.call_args[0][0]
        assert "users" in args.belownodes

@pytest.mark.unit
def test_nuke_function():
    """Test nuke() function"""
    from unittest.mock import patch
    from dbsamizdat import nuke

    with patch('dbsamizdat.api._cmd_nuke') as mock_nuke:
        nuke("postgresql:///test")
        mock_nuke.assert_called_once()

@pytest.mark.unit
def test_api_functions_use_default_dburl():
    """Test that API functions use DBURL env var when dburl not provided"""
    import os
    from unittest.mock import patch
    from dbsamizdat import sync

    os.environ['DBURL'] = 'postgresql:///default'
    with patch('dbsamizdat.api._cmd_sync') as mock_sync:
        sync()
        args = mock_sync.call_args[0][0]
        assert args.dburl == 'postgresql:///default'
    del os.environ['DBURL']
```

**Expected Coverage Gain**: +2.5%

### 2. GraphViz DOT Generation (`dbsamizdat/graphvizdot.py` - 17.65% coverage)

**Impact**: Medium - Useful for debugging dependency graphs
**Effort**: Low - Pure function, no database needed

**Tests Needed**:
```python
# tests/test_graphvizdot.py
@pytest.mark.unit
def test_dot_simple_view():
    """Test dot() generates valid GraphViz for simple view"""
    from dbsamizdat.graphvizdot import dot
    from dbsamizdat import SamizdatView

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    output = list(dot([TestView]))
    dot_str = "\n".join(output)
    assert 'digraph' in dot_str
    assert 'TestView' in dot_str
    assert 'shape=box' in dot_str  # VIEW shape

@pytest.mark.unit
def test_dot_materialized_view():
    """Test dot() generates correct shape for materialized views"""
    from dbsamizdat.graphvizdot import dot
    from dbsamizdat import SamizdatMaterializedView

    class TestMatView(SamizdatMaterializedView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    output = list(dot([TestMatView]))
    dot_str = "\n".join(output)
    assert 'shape=box3d' in dot_str  # MATVIEW shape
    assert 'fillcolor=red' in dot_str

@pytest.mark.unit
def test_dot_with_dependencies():
    """Test dot() shows dependency edges"""
    from dbsamizdat.graphvizdot import dot
    from dbsamizdat import SamizdatView

    class BaseView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    class DependentView(SamizdatView):
        deps_on = {BaseView}
        sql_template = "${preamble} SELECT * FROM \"BaseView\" ${postamble}"

    output = list(dot([BaseView, DependentView]))
    dot_str = "\n".join(output)
    assert 'BaseView' in dot_str
    assert 'DependentView' in dot_str
    assert '->' in dot_str  # Dependency edge

@pytest.mark.unit
def test_dot_with_unmanaged_dependencies():
    """Test dot() shows unmanaged dependencies"""
    from dbsamizdat.graphvizdot import dot
    from dbsamizdat import SamizdatView

    class ViewWithUnmanaged(SamizdatView):
        deps_on_unmanaged = {"public", "users"}
        sql_template = "${preamble} SELECT * FROM users ${postamble}"

    output = list(dot([ViewWithUnmanaged]))
    dot_str = "\n".join(output)
    assert 'shape=house' in dot_str  # Unmanaged nodes
    assert 'fillcolor=yellow' in dot_str
```

**Expected Coverage Gain**: +15%

### 3. CLI Argument Parsing (`dbsamizdat/runner/cli.py` - 14.55% coverage)

**Impact**: Medium - Important for CLI usability
**Effort**: Low - Can test argument parsing without database

**Tests Needed**:
```python
# tests/test_cli.py
@pytest.mark.unit
def test_augment_argument_parser_adds_subcommands():
    """Test that augment_argument_parser adds all expected subcommands"""
    import argparse
    from dbsamizdat.runner.cli import augment_argument_parser

    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Check subcommands exist
    subcommands = [action.dest for action in parser._actions if hasattr(action, 'dest')]
    assert 'func' in subcommands

@pytest.mark.unit
def test_cli_requires_modules_when_not_django():
    """Test that CLI requires samizdatmodules when not in Django"""
    import argparse
    from dbsamizdat.runner.cli import augment_argument_parser

    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=False)

    # Try parsing without modules - should fail
    with pytest.raises(SystemExit):
        parser.parse_args(['sync', 'postgresql:///test'])

@pytest.mark.unit
def test_cli_django_mode_uses_dbconn():
    """Test that Django mode uses dbconn instead of dburl"""
    import argparse
    from dbsamizdat.runner.cli import augment_argument_parser

    parser = argparse.ArgumentParser()
    augment_argument_parser(parser, in_django=True)

    args = parser.parse_args(['sync', 'custom_conn'])
    assert args.dbconn == 'custom_conn'

@pytest.mark.unit
def test_main_handles_samizdat_exception():
    """Test that main() handles SamizdatException gracefully"""
    from unittest.mock import patch, MagicMock
    from dbsamizdat.runner.cli import main
    from dbsamizdat.exceptions import SamizdatException

    with patch('sys.argv', ['dbsamizdat', 'sync', 'postgresql:///test', 'module']):
        with patch('dbsamizdat.runner.cli.augment_argument_parser') as mock_parser:
            mock_args = MagicMock()
            mock_args.func = MagicMock(side_effect=SamizdatException("Test error"))
            mock_parser.return_value.parse_args.return_value = mock_args

            with pytest.raises(SystemExit):
                main()
```

**Expected Coverage Gain**: +25%

## Priority 2: Integration Tests (Can reach ~70%)

### 4. Command Functions (`dbsamizdat/runner/commands.py` - 18.48% coverage)

**Impact**: High - Core functionality
**Effort**: Medium - Requires database but tests are straightforward

**Tests Needed**:
```python
# tests/test_commands.py (additions)
@pytest.mark.integration
def test_cmd_sync_with_module_names(clean_db):
    """Test cmd_sync works with samizdatmodules"""
    from dbsamizdat.runner import cmd_sync, ArgType

    args = ArgType(
        dburl=clean_db.dburl,
        samizdatmodules=["sample_app.dbsamizdat_defs"],
        in_django=False
    )
    cmd_sync(args)
    # Verify objects were created

@pytest.mark.integration
def test_cmd_refresh_with_belownodes(clean_db):
    """Test cmd_refresh filters by belownodes"""
    # Create some views
    # Refresh with belownodes filter
    # Verify only filtered views were refreshed

@pytest.mark.integration
def test_cmd_diff_shows_differences(clean_db):
    """Test cmd_diff correctly identifies differences"""
    # Create some views
    # Drop one manually
    # Run diff
    # Verify it detects the difference

@pytest.mark.integration
def test_cmd_printdot_output(clean_db):
    """Test cmd_printdot generates valid DOT output"""
    from dbsamizdat.runner import cmd_printdot, ArgType
    from io import StringIO
    import sys

    args = ArgType(
        dburl=clean_db.dburl,
        samizdatmodules=["sample_app.dbsamizdat_defs"],
        in_django=False
    )

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        cmd_printdot(args)
        output = sys.stdout.getvalue()
        assert 'digraph' in output
    finally:
        sys.stdout = old_stdout
```

**Expected Coverage Gain**: +30%

### 5. Executor Function (`dbsamizdat/runner/executor.py` - 22.50% coverage)

**Impact**: High - Core execution engine
**Effort**: Medium - Requires database

**Tests Needed**:
```python
# tests/test_executor.py
@pytest.mark.integration
def test_executor_progress_reporting(clean_db):
    """Test executor prints progress with verbosity"""
    from dbsamizdat.runner import executor, ArgType
    from dbsamizdat.samizdat import SamizdatView

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    args = ArgType(verbosity=2, dburl=clean_db.dburl)
    with get_cursor(args) as cursor:
        def actions():
            yield "create", TestView, TestView.create()
            yield "sign", TestView, TestView.sign(cursor)

        executor(actions(), args, cursor, timing=True)
        # Verify output was printed

@pytest.mark.integration
def test_executor_handles_errors(clean_db):
    """Test executor raises DatabaseError on SQL errors"""
    from dbsamizdat.runner import executor, ArgType
    from dbsamizdat.exceptions import DatabaseError

    args = ArgType(dburl=clean_db.dburl)
    with get_cursor(args) as cursor:
        def bad_actions():
            yield "create", None, "INVALID SQL SYNTAX;"

        with pytest.raises(DatabaseError):
            executor(bad_actions(), args, cursor)

@pytest.mark.integration
def test_executor_checkpoint_mode(clean_db):
    """Test executor commits after each action in checkpoint mode"""
    from dbsamizdat.runner import executor, ArgType, txstyle

    args = ArgType(
        dburl=clean_db.dburl,
        txdiscipline=txstyle.CHECKPOINT.value
    )
    # Test that commits happen at checkpoints
```

**Expected Coverage Gain**: +20%

## Priority 3: Edge Cases and Error Handling

### 6. Exception Handling (`dbsamizdat/exceptions.py` - 56.10% coverage)

**Impact**: Medium - Better error messages
**Effort**: Low - Can test exception creation

**Tests Needed**:
```python
# tests/test_exceptions.py
@pytest.mark.unit
def test_database_error_formatting():
    """Test DatabaseError formats error message correctly"""
    from dbsamizdat.exceptions import DatabaseError
    from dbsamizdat.samizdat import SamizdatView

    class TestView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    error = Exception("SQL syntax error")
    db_error = DatabaseError("create failed", error, TestView, "CREATE VIEW...")

    assert "create failed" in str(db_error)
    assert "TestView" in str(db_error)

@pytest.mark.unit
def test_function_signature_error():
    """Test FunctionSignatureError shows candidate signatures"""
    from dbsamizdat.exceptions import FunctionSignatureError
    from dbsamizdat.samizdat import SamizdatFunction

    class TestFunc(SamizdatFunction):
        sql_template = "${preamble} RETURNS TEXT AS $BODY$ SELECT 1 $BODY$"

    error = FunctionSignatureError(TestFunc, ["text", "integer"])
    assert "candidate" in str(error).lower() or "signature" in str(error).lower()
```

**Expected Coverage Gain**: +10%

### 7. Utility Functions (`dbsamizdat/util.py` - 41.67% coverage)

**Impact**: Low - Utility functions
**Effort**: Low - Simple unit tests

**Tests Needed**:
```python
# tests/test_util.py
@pytest.mark.unit
def test_nodenamefmt():
    """Test nodenamefmt formats node names correctly"""
    from dbsamizdat.util import nodenamefmt
    from dbsamizdat.samtypes import FQTuple

    fq = FQTuple("public", "MyView")
    assert nodenamefmt(fq) == "public.MyView"

    # Test with tuple
    assert nodenamefmt(("public", "MyView")) == "public.MyView"
```

**Expected Coverage Gain**: +5%

## Priority 4: Django Integration

### 8. Django API (`dbsamizdat/django_api.py` - 0% coverage)

**Impact**: Medium - Important for Django users
**Effort**: Medium - Requires Django setup

**Tests Needed**:
```python
# tests/test_django_api.py
@pytest.mark.django
def test_django_sync_function(django_setup):
    """Test django_api.sync() function"""
    from dbsamizdat import django_api

    django_api.sync()
    # Verify samizdats were synced

@pytest.mark.django
def test_django_refresh_function(django_setup):
    """Test django_api.refresh() function"""
    from dbsamizdat import django_api

    django_api.refresh()
    # Verify materialized views were refreshed
```

**Expected Coverage Gain**: +2%

## Implementation Strategy

### Phase 1: Quick Wins (Target: 65% coverage)
1. ✅ Add tests for `api.py` functions (mocked)
2. ✅ Add tests for `graphvizdot.py`
3. ✅ Add tests for `cli.py` argument parsing
4. ✅ Add tests for exception formatting

**Estimated Time**: 2-3 hours
**Expected Coverage**: 65%

### Phase 2: Integration Tests (Target: 70% coverage)
1. ✅ Add integration tests for command functions
2. ✅ Add tests for executor function
3. ✅ Add tests for edge cases

**Estimated Time**: 4-6 hours
**Expected Coverage**: 70%

### Phase 3: Django and Edge Cases (Target: 75%+ coverage)
1. ✅ Add Django API tests
2. ✅ Add more edge case tests
3. ✅ Add tests for error recovery

**Estimated Time**: 3-4 hours
**Expected Coverage**: 75%+

## Testing Best Practices

1. **Use mocks for external dependencies** - Don't require database for unit tests
2. **Test error paths** - Exception handling is often untested
3. **Test edge cases** - Empty lists, None values, boundary conditions
4. **Test with different verbosity levels** - Many functions have verbosity-dependent behavior
5. **Test transaction disciplines** - CHECKPOINT vs JUMBO vs DRYRUN

## Files to Create

- `tests/test_api.py` - Library API tests
- `tests/test_graphvizdot.py` - GraphViz generation tests
- `tests/test_cli.py` - CLI argument parsing tests
- `tests/test_executor.py` - Executor function tests
- `tests/test_exceptions.py` - Exception formatting tests
- `tests/test_util.py` - Utility function tests
- `tests/test_django_api.py` - Django API tests

## Notes

- Many integration tests require a database, which is why they're currently skipped
- Focus on unit tests first (no database needed) for quick coverage gains
- Mock database cursors where possible to test logic without database
- Use `@pytest.mark.unit` for tests that don't need a database
- Use `@pytest.mark.integration` for tests that need a database
