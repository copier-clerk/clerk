default:
    @just --list

# Run tests
test:
    uv run pytest

# Lint and format
lint:
    pre-commit run --all-files

# Type-check
types:
    uv run mypy

# Build
build:
    uv build

# Start dev server
dev:
    @echo "INFO: clerk is a CLI/library — no dev server. Use 'just test' or run 'uv run clerk'." && exit 1

# Clean build artifacts
clean:
    rm -rf dist build .pytest_cache .ruff_cache .mypy_cache
