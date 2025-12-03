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
uv run pytest
```

**Run unit tests only:**
```bash
uv run pytest -m unit
```

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

Spin up a podman or docker container for integration tests:

```bash
podman run -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres
# or
docker run -p 5435:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:latest
```

The db url for this container would be:
```
postgresql:///postgres@localhost:5435/postgres
```

Make this the environment variable `DB_URL`, or add it to the `.env` file.

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Run linting: `uv run ruff check . --fix`
6. Format code: `uv run ruff format .`
7. Commit using [conventional commits](https://www.conventionalcommits.org/)
8. Submit a pull request

## Resources

- [Pre-commit installation with uv](https://adamj.eu/tech/2025/05/07/pre-commit-install-uv/) - Recommended installation method
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [UV documentation](https://github.com/astral-sh/uv)
