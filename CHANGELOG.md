# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Function signature handling documentation (Issue #7)
  - Clear explanation of two approaches for creating functions (Option A: full CREATE FUNCTION, Option B: using `${preamble}`)
  - Complete examples for functions with no parameters, with parameters, and returning tables
  - Common pitfalls section covering signature duplication, empty signature behavior, and missing CREATE FUNCTION errors
  - Comprehensive troubleshooting guide in USAGE.md
- Comprehensive template variable reference (Issue #8)
  - Complete reference of all available template variables (`${preamble}`, `${postamble}`, `${samizdatname}`) by entity type
  - Detailed documentation for function references in triggers using `creation_identity()` method
  - Examples showing template variable usage in functions, triggers, views, tables, and materialized views
  - Template Variable Summary Table for quick reference
- Best Practices and Common Patterns guide (Issue #10)
  - Function Creation Checklist with actionable steps
  - Trigger Creation Checklist with actionable steps
  - Common Patterns section with complete working examples:
    - Simple function (no parameters)
    - Function with parameters
    - Trigger calling function
    - Multi-function dependencies
  - Quick Reference section highlighting common mistakes to avoid
  - Comprehensive test suite (`tests/test_best_practices.py`) verifying all documented patterns
- Enhanced error messages for SQL template processing failures (Issue #9)
  - Error messages now show original template, template variable substitutions, and function signature context
  - Automatic detection of common error patterns with helpful hints:
    - Signature duplication detection
    - Missing CREATE FUNCTION detection
    - Invalid template variable detection
  - Comprehensive troubleshooting documentation in USAGE.md with debugging tips
- Comprehensive integration tests for database operations (30 new tests covering cmd_sync, cmd_refresh, cmd_nuke, cmd_diff, executor, and libdb)
- Unit tests for module import functionality (`tests/test_module_import.py`)
- Unit tests for CLI argument parsing and command execution (`tests/test_cli.py`)
- Unit tests for library API functions (`tests/test_api.py`)
- Unit tests for exception handling (`tests/test_exceptions.py`)
- Unit tests for utility functions (`tests/test_util.py`)
- Unit tests for GraphViz DOT generation (`tests/test_graphvizdot.py`)
- Pre-commit hooks with ruff for automated linting and formatting
- Test coverage reporting with pytest-cov (currently 83.10% coverage)
- Comprehensive usage documentation (`USAGE.md`) with examples for non-Django and Django usage
- Example code demonstrating basic usage patterns (`examples/simple_example.py`)
- Pre-commit installation guide in README with link to uv-based installation
- Module import functionality: CLI and API now properly import modules specified via `samizdatmodules` argument
- `import_samizdat_modules()` function for dynamic module importing

### Changed
- Replaced black, isort, and flake8 with ruff for faster linting and formatting
- Updated GraphViz dot() to use f-strings instead of % formatting for better readability
- Improved error messages and documentation throughout codebase
- Test coverage threshold set to 55% (currently at 83.10%)

### Fixed
- Module discovery bug: CLI now properly imports modules specified via `samizdatmodules` argument instead of relying on manual imports
- Autodiscovery robustness: Added error handling for Django availability and module import failures to prevent silent failures when discovering `dbsamizdat_defs` files
- GraphViz dot() now correctly handles TABLE entity types (was missing from styles dictionary)
- GraphViz dot() now handles empty samizdat lists without IndexError when accessing `topsorted[-1]`
- cmd_refresh now filters to only refresh materialized views that exist in the database, preventing errors when code defines matviews that haven't been synced
- Fixed test failures related to SystemExit handling in cmd_diff tests (cmd_diff calls exit())
- Fixed test failures related to class object vs FQTuple comparisons in libdb tests
- Fixed unused variable warnings in test code

## [0.1.0] - 2024-01-XX

### Added
- Initial release
- Support for PostgreSQL views, materialized views, functions, and triggers
- Django integration with autodiscovery
- CLI interface for sync, refresh, nuke, diff, and printdot commands
- Library API for programmatic usage
- Dependency graph management
- GraphViz DOT output for visualization
- Transaction discipline options (checkpoint, jumbo, dryrun)

### Changed
- Modernized codebase to use Python 3.12+ features
- Refactored runner.py into focused modules following SOLID principles
- Replaced manual cursor handling with Protocol-based approach

### Fixed
- Various bug fixes from modernization effort

[Unreleased]: https://github.com/catalpainternational/dbsamizdapper/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/catalpainternational/dbsamizdapper/releases/tag/v0.1.0
