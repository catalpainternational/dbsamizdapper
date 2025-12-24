# Justfile for dbsamizdapper development tasks

# Default recipe - show available commands
default:
    @just --list

# PostgreSQL port (default: 5435)
POSTGRES_PORT := "5435"

# PostgreSQL version (default: 15)
POSTGRES_VERSION := "15"

# Start PostgreSQL container
start-db:
    #!/usr/bin/env bash
    set -e
    if ! command -v podman > /dev/null; then
        echo "Error: podman command not found"
        exit 1
    fi
    # Check if container already exists and is running
    if podman ps --filter name=dbsamizdapper-postgres -q | grep -q .; then
        echo "PostgreSQL container is already running"
        exit 0
    fi
    # Check if port is available (only if container is not running)
    PORT_IN_USE=false
    if command -v lsof > /dev/null 2>&1; then
        if lsof -Pi :{{POSTGRES_PORT}} -sTCP:LISTEN > /dev/null 2>&1; then
            PORT_IN_USE=true
        fi
    elif command -v ss > /dev/null 2>&1; then
        if ss -lntu 2>/dev/null | grep -q ":{{POSTGRES_PORT}}"; then
            PORT_IN_USE=true
        fi
    elif command -v netstat > /dev/null 2>&1; then
        if netstat -lntu 2>/dev/null | grep -q ":{{POSTGRES_PORT}}"; then
            PORT_IN_USE=true
        fi
    fi
    if [ "$PORT_IN_USE" = true ]; then
        echo "Error: Port {{POSTGRES_PORT}} is already in use"
        exit 1
    fi
    # Remove existing stopped container if it exists
    if podman ps -a --filter name=dbsamizdapper-postgres -q | grep -q .; then
        podman rm dbsamizdapper-postgres > /dev/null 2>&1 || true
    fi
    # Start container
    podman run -d \
        --name dbsamizdapper-postgres \
        -p {{POSTGRES_PORT}}:5432 \
        -e POSTGRES_HOST_AUTH_METHOD=trust \
        docker.io/library/postgres:{{POSTGRES_VERSION}}
    echo "Waiting for PostgreSQL to be ready..."
    timeout=30
    while [ $timeout -gt 0 ]; do
        if podman exec dbsamizdapper-postgres pg_isready -U postgres > /dev/null 2>&1; then
            echo "PostgreSQL is ready!"
            exit 0
        fi
        sleep 1
        timeout=$((timeout - 1))
    done
    echo "PostgreSQL failed to start within 30 seconds"
    exit 1

# Stop PostgreSQL container
stop-db:
    #!/usr/bin/env bash
    set -e
    if ! command -v podman > /dev/null; then
        echo "Error: podman command not found"
        exit 1
    fi
    if podman ps --filter name=dbsamizdapper-postgres -q | grep -q .; then
        podman stop dbsamizdapper-postgres
        podman rm dbsamizdapper-postgres
        echo "PostgreSQL container stopped and removed"
    else
        echo "PostgreSQL container is not running"
    fi

# Run all tests in a containerized environment
test:
    #!/usr/bin/env bash
    set -e
    if ! command -v podman > /dev/null; then
        echo "Error: podman command not found"
        exit 1
    fi
    # Check if container already exists and is running
    if podman ps --filter name=dbsamizdapper-postgres -q | grep -q .; then
        echo "PostgreSQL container is already running"
    else
        # Check if port is available (only if container is not running)
        PORT_IN_USE=false
        if command -v lsof > /dev/null 2>&1; then
            if lsof -Pi :{{POSTGRES_PORT}} -sTCP:LISTEN > /dev/null 2>&1; then
                PORT_IN_USE=true
            fi
        elif command -v ss > /dev/null 2>&1; then
            if ss -lntu 2>/dev/null | grep -q ":{{POSTGRES_PORT}}"; then
                PORT_IN_USE=true
            fi
        elif command -v netstat > /dev/null 2>&1; then
            if netstat -lntu 2>/dev/null | grep -q ":{{POSTGRES_PORT}}"; then
                PORT_IN_USE=true
            fi
        fi
        if [ "$PORT_IN_USE" = true ]; then
            echo "Error: Port {{POSTGRES_PORT}} is already in use"
            exit 1
        fi
        # Remove existing stopped container if it exists
        if podman ps -a --filter name=dbsamizdapper-postgres -q | grep -q .; then
            podman rm dbsamizdapper-postgres > /dev/null 2>&1 || true
        fi
        echo "Starting PostgreSQL container..."
        podman run -d \
            --name dbsamizdapper-postgres \
            -p {{POSTGRES_PORT}}:5432 \
            -e POSTGRES_HOST_AUTH_METHOD=trust \
            docker.io/library/postgres:{{POSTGRES_VERSION}}
        echo "Waiting for PostgreSQL to be ready..."
        timeout=30
        while [ $timeout -gt 0 ]; do
            if podman exec dbsamizdapper-postgres pg_isready -U postgres > /dev/null 2>&1; then
                echo "PostgreSQL is ready!"
                break
            fi
            sleep 1
            timeout=$((timeout - 1))
        done
        if [ $timeout -eq 0 ]; then
            echo "PostgreSQL failed to start within 30 seconds"
            podman stop dbsamizdapper-postgres > /dev/null 2>&1 || true
            podman rm dbsamizdapper-postgres > /dev/null 2>&1 || true
            exit 1
        fi
    fi
    echo "Setting environment variables..."
    export DB_PORT={{POSTGRES_PORT}}
    export POSTGRES_VERSION={{POSTGRES_VERSION}}
    echo "Syncing dependencies with all extras..."
    uv sync --group dev --group testing --extra django --extra psycopg3
    echo "Running tests..."
    uv run pytest
    echo "Tests completed. Tearing down container..."
    podman stop dbsamizdapper-postgres > /dev/null 2>&1 || true
    podman rm dbsamizdapper-postgres > /dev/null 2>&1 || true

# Run tests without starting/stopping container (assumes DB is already running)
test-only:
    #!/usr/bin/env bash
    set -e
    export DB_PORT={{POSTGRES_PORT}}
    echo "Syncing dependencies with all extras..."
    uv sync --group dev --group testing --extra django --extra psycopg3
    echo "Running tests..."
    uv run pytest

# Run unit tests only (no database required)
test-unit:
    uv run pytest -m unit

# Run integration tests only (requires database)
test-integration:
    #!/usr/bin/env bash
    set -e
    export DB_PORT={{POSTGRES_PORT}}
    uv run pytest -m integration

# Run tests with coverage report
test-coverage:
    #!/usr/bin/env bash
    set -e
    export DB_PORT={{POSTGRES_PORT}}
    uv sync --group dev --group testing --extra django --extra psycopg3
    uv run pytest --cov=dbsamizdat --cov-report=term-missing --cov-report=html

# Clean up test artifacts
clean:
    rm -rf .pytest_cache
    rm -rf htmlcov
    rm -rf .coverage
    rm -rf .mypy_cache
    find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Lint with ruff
lint:
    uv run ruff check .

# Check code formatting with ruff
format-check:
    uv run ruff format --check .

# Format code with ruff (apply fixes)
format:
    uv run ruff format .

# Type check with mypy
typecheck:
    uv run mypy dbsamizdat

# Run all CI checks (lint, format, typecheck) - matches GitHub Actions
ci: lint format-check typecheck
    @echo "✅ All CI checks passed!"

# Fix linting issues automatically
fix:
    uv run ruff check --fix .
    uv run ruff format .
