# Development Guide

## Setup

This project uses [UV](https://github.com/astral-sh/uv) for fast dependency management.

### Install UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

### Install Dependencies

```bash
# Clone the repository
git clone <repo-url>
cd dbsamizdapper

# Install dependencies (includes dev tools)
uv sync --group dev --group testing

# Optional: Install Django type stubs for Django integration development
uv sync --group dev --group testing --extra django
```

## Code Quality Tools

### Ruff (Linting & Formatting)

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting, replacing black, isort, and flake8.

**Format code:**
```bash
uv run ruff format .
```

**Check and fix linting issues:**
```bash
uv run ruff check . --fix
```

**Check only (no fixes):**
```bash
uv run ruff check .
```

### Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) for automated code quality checks.

**Installation:**

We recommend installing pre-commit using [uv](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/):

```bash
# Install pre-commit with uv (includes pre-commit-uv for faster Python hook installation)
uv tool install pre-commit --with pre-commit-uv

# Install Git hooks (runs automatically on commit)
pre-commit install
```

**Usage:**

```bash
# Run on all files manually
pre-commit run --all-files

# Run on staged files only (default behavior on commit)
pre-commit run

# Run a specific hook
pre-commit run ruff --all-files
pre-commit run mypy --all-files

# Run only files that have changed
pre-commit run --files dbsamizdat/api.py

# Update pre-commit hooks to latest versions
pre-commit autoupdate

# Upgrade pre-commit itself
uv tool upgrade pre-commit

# Uninstall Git hooks (if needed)
pre-commit uninstall
```

**How it works:**

1. When you run `git commit`, pre-commit automatically runs configured hooks
2. If any hook fails, the commit is blocked
3. Hooks can auto-fix some issues (e.g., ruff formatting)
4. After fixes, you need to stage the changes and commit again

**Skipping hooks (not recommended):**

```bash
# Skip pre-commit hooks for a single commit
git commit --no-verify -m "your message"
```

**Troubleshooting:**

```bash
# Clear pre-commit cache if hooks are misbehaving
pre-commit clean

# See what hooks would run
pre-commit run --all-files --verbose

# Test hooks without installing
pre-commit run --all-files --hook-stage manual
```

The pre-commit configuration (`.pre-commit-config.yaml`) includes:
- Ruff (linting and formatting)
- MyPy (type checking)
- Common pre-commit hooks (trailing whitespace, file checks, etc.)

## Development Commands

**Run tests:**
```bash
# Ensure database is ready first (see TESTING.md for setup)
uv run pytest
```

**Run unit tests only:**
```bash
# Unit tests don't require a database
uv run pytest -m unit
```

**Note**: Always use `uv run pytest` (not `pytest` or `python -m pytest`) to ensure dependencies are available in the virtual environment.

**Run with coverage:**
```bash
uv run pytest --cov=dbsamizdat --cov-report=term-missing
```

**Type checking:**
```bash
uv run mypy dbsamizdat
```

**Build package:**
```bash
uv build
```

## Running Tests

> **For comprehensive testing guide, see [TESTING.md](TESTING.md)**

### Quick Start

**Start PostgreSQL database:**
```bash
docker-compose up -d
# Or manually:
docker run -d -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15
```

**Set database connection:**
```bash
export DB_URL=postgresql://postgres@localhost:5435/postgres
# Or create .env file (see .env.example)
```

**Run tests:**
```bash
# All tests (requires database - ensure it's ready first!)
uv run pytest

# Unit tests only (no database required)
uv run pytest -m unit
```

**Important**: Always use `uv run pytest` (not `pytest` or `python -m pytest`) to ensure dependencies are available in the virtual environment. For integration tests, ensure the PostgreSQL database is running and configured (see [TESTING.md](TESTING.md) for setup instructions).

See [TESTING.md](TESTING.md) for detailed testing instructions, troubleshooting, and advanced usage.

## Code Style

- **Line length**: 119 characters
- **Python version**: 3.12+
- **Formatter**: Ruff (replaces black/isort)
- **Linter**: Ruff (replaces flake8)
- **Type checker**: MyPy

## Project Structure

```
dbsamizdapper/
├── dbsamizdat/          # Main package
│   ├── runner/          # CLI and command execution
│   └── ...
├── tests/               # Test suite
├── examples/            # Example code
├── sample_app/          # Sample Django app for testing
└── docs/                # Documentation
```

## Changelog Maintenance

This project maintains a changelog in `CHANGELOG.md` following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

### When to Update the Changelog

Update `CHANGELOG.md` when making **significant changes** including:
- New features or functionality
- Breaking changes to APIs or behavior
- Bug fixes that affect user experience
- Security updates
- Deprecations
- Performance improvements
- Documentation improvements that significantly change usage

**Do NOT update for:**
- Minor refactoring that doesn't change behavior
- Test-only changes
- Internal code improvements with no user impact
- Documentation typo fixes

### How to Update

1. Add entries to the `[Unreleased]` section
2. Use appropriate categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`
3. Use clear, user-focused descriptions
4. Link to relevant issues/PRs when applicable
5. When releasing a version, move `[Unreleased]` entries to a new version section

### Example Entry

```markdown
### Fixed
- cmd_refresh now filters to only refresh materialized views that exist in the database
- Fixed GraphViz dot() IndexError when handling empty samizdat lists
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Run linting: `uv run ruff check . --fix`
6. Format code: `uv run ruff format .`
7. Update `CHANGELOG.md` if changes are significant (see above)
8. Commit using [conventional commits](https://www.conventionalcommits.org/)
9. Submit a pull request

## Resources

- [Pre-commit installation with uv](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/) - Recommended installation method
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [UV documentation](https://github.com/astral-sh/uv)
