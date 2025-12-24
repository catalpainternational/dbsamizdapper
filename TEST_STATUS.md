# Test Status

> **Note**: This file is outdated. For current testing information, see [TESTING.md](TESTING.md).

## Test Results Summary

**Date**: Last Updated (Outdated)
**Total Tests**: ~146+ (exact count may vary)
**Status**: ✅ All tests that don't require a database are passing

### Test Breakdown

- ✅ **47 passed** - Unit tests (no database required)
- ⚠️ **1 skipped** - Expected skips (conditional tests)
- ❌ **1 error** - Database connection required (`test_signing_requires_cursor`)
- ❌ **3 failed** - Database connection required
- ❌ **20 errors** - Database connection required (integration tests)

### Tests Requiring Database

The following tests require a running PostgreSQL instance on `localhost:5435`:

- Integration tests in `test_sample.py`
- Integration tests in `test_samizdat_table.py`
- Integration tests in `test_trigger_lsp.py`
- Integration tests in `test_cursor_protocol.py`

To run these tests, see [TESTING.md](TESTING.md) for complete setup instructions.

**Quick start:**
```bash
# Start database
docker-compose up -d

# Set connection
export DB_URL=postgresql://postgres@localhost:5435/postgres

# Run tests
uv run pytest
```

### All Unit Tests Pass ✅

All unit tests (marked with `@pytest.mark.unit`) pass successfully:

- Module import functionality ✅
- Template processing ✅
- Type checking ✅
- Dependency resolution ✅
- SQL generation ✅
- Validation logic ✅

### New Tests Added

The following new tests were added for module import functionality:

- `test_import_samizdat_modules_single_module` ✅
- `test_import_samizdat_modules_multiple_modules` ✅
- `test_import_samizdat_modules_nonexistent_module` ✅
- `test_get_sds_with_module_names` ✅
- `test_get_sds_without_modules_uses_autodiscovery` ✅
- `test_get_sds_explicit_list_takes_precedence` ✅

All new tests pass successfully.

## Running Tests

For detailed testing instructions, see [TESTING.md](TESTING.md).

**Quick reference:**
- Unit tests: `uv run pytest -m unit`
- All tests: `uv run pytest` (requires database)
- See [TESTING.md](TESTING.md) for complete guide
