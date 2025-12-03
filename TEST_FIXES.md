# Test Fixes Needed

## Overview

We have 7 failing tests out of 30 new integration tests. All tests are structurally correct but need minor adjustments to match the actual API behavior.

## Failing Tests and Fixes

### 1. `test_cmd_refresh_refreshes_all_materialized_views`

**Issue**: The test verifies materialized views exist, but doesn't verify they were actually refreshed.

**Fix**: Add a check that verifies the materialized view has data or check refresh timestamp:
```python
# After cmd_refresh, verify the materialized view has been refreshed
with get_cursor(args) as cursor:
    cursor.execute("""
        SELECT COUNT(*) FROM pg_matviews
        WHERE schemaname = 'public'
        AND matviewname IN ('MaterializedView', 'AnotherMaterializedView')
    """)
    assert cursor.fetchone()[0] == 2

    # Verify they have data
    cursor.execute('SELECT COUNT(*) FROM "MaterializedView"')
    assert cursor.fetchone()[0] > 0
```

### 2. `test_cmd_refresh_empty_when_no_materialized_views`

**Issue**: The test may be checking for an error when there are no materialized views, but `cmd_refresh` should handle this gracefully.

**Fix**: Verify that `cmd_refresh` completes without error when there are no materialized views:
```python
# This should not raise an error
cmd_refresh(args)

# Verify no materialized views exist
with get_cursor(args) as cursor:
    cursor.execute("""
        SELECT COUNT(*) FROM pg_matviews
        WHERE schemaname = 'public'
    """)
    assert cursor.fetchone()[0] == 0
```

### 3. `test_cmd_diff_shows_no_differences_when_synced`

**Issue**: `cmd_diff` prints to stdout and exits with a code, but doesn't return a value we can easily test.

**Fix**: Capture stdout or check exit code:
```python
from io import StringIO
import sys

# Capture stdout
old_stdout = sys.stdout
sys.stdout = captured_output = StringIO()

try:
    with get_cursor(args) as cursor:
        cmd_diff(args)
    output = captured_output.getvalue()
    # Verify output indicates no differences
    assert "no differences" in output.lower() or "same" in output.lower()
finally:
    sys.stdout = old_stdout
```

Alternatively, check the exit code if `cmd_diff` uses `sys.exit()`:
```python
# cmd_diff may exit with code 0 when no differences
# We can't easily test this without mocking sys.exit
# Consider making cmd_diff return a value instead
```

### 4. `test_cmd_diff_shows_differences_when_unsynced`

**Issue**: Same as above - `cmd_diff` prints to stdout, hard to test.

**Fix**: Same approach as #3, or refactor `cmd_diff` to return a result object:
```python
# Similar to test_cmd_diff_shows_no_differences_when_synced
# Capture and verify output contains difference information
```

### 5. `test_executor_handles_multiple_operations`

**Issue**: The test defines a class inside the test function, which may cause issues with class registration.

**Fix**: Define the class at module level or use a different approach:
```python
# Define at module level
class View1(SamizdatView):
    sql_template = "${preamble} SELECT 1 ${postamble}"

class View2(SamizdatView):
    sql_template = "${preamble} SELECT 2 ${postamble}"

@pytest.mark.integration
def test_executor_handles_multiple_operations(clean_db):
    args = clean_db
    args.samizdatmodules = []

    # Use the module-level classes
    cmd_sync(args, [View1, View2])

    # Rest of test...
```

### 6. `test_dbstate_equals_definedstate_detects_missing_views`

**Issue**: The test checks if `AnotherTestView.fq()` is in `result.excess_definedstate`, but `excess_definedstate` contains class objects, not FQTuples.

**Fix**: Check for the class object directly:
```python
assert result.issame is False
# excess_definedstate contains class objects
excess_classes = set(result.excess_definedstate)
assert AnotherTestView in excess_classes
```

### 7. `test_dbstate_equals_definedstate_ignores_non_dbsamizdat_views`

**Issue**: The test creates a manual view without a dbsamizdat comment, but `get_dbstate` only returns views with dbsamizdat comments, so the manual view won't appear in `excess_dbstate`.

**Fix**: The test logic is correct, but we need to verify that `get_dbstate` indeed filters out views without comments:
```python
# Create manual view
with get_cursor(args) as cursor:
    cursor.execute("CREATE VIEW manual_view AS SELECT 1;")

# Verify get_dbstate doesn't return it
with get_cursor(args) as cursor:
    dbstate = list(get_dbstate(cursor))
    manual_view_states = [
        s for s in dbstate
        if s.schemaname == "public" and s.viewname == "manual_view"
    ]
    assert len(manual_view_states) == 0  # Should be filtered out

# Then check dbstate_equals_definedstate
with get_cursor(args) as cursor:
    result = dbstate_equals_definedstate(cursor, [])
    # excess_dbstate should be empty since manual_view has no comment
    assert len(result.excess_dbstate) == 0
```

## General Recommendations

1. **For `cmd_diff` tests**: Consider refactoring `cmd_diff` to return a result object instead of printing and exiting, making it easier to test.

2. **For class definitions in tests**: Always define test classes at module level to avoid issues with class registration and discovery.

3. **For output verification**: Use `capsys` or `StringIO` to capture stdout when testing functions that print.

4. **For state comparison tests**: Remember that:
   - `excess_definedstate` contains class objects (SamizType)
   - `excess_dbstate` contains reconstructed class objects (from `dbinfo_to_class`)
   - Use `.fq()` method to get FQTuple for comparison

## Quick Fix Summary

1. Move class definitions to module level
2. Use `capsys` fixture for stdout capture
3. Fix `excess_definedstate` checks to use class objects
4. Verify `get_dbstate` filtering behavior
5. Add data verification for refresh tests
