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

# ---------------------------------------------------------------------------
# APM packaging (spec 008)
# ---------------------------------------------------------------------------

# BLOCKER-2 guard: vendor MUST run before apm pack because --check-clean only
# diffs manifests, not the vendored copy. `just pack` / `just release` both
# run vendor first so a stale vendored tree can never ship.

VENDOR_DST := "packages/clerk/.apm/skills/clerk/scripts/clerk"
VENDOR_SRC := "src/clerk"

# Copy src/clerk/*.py (by glob, auto-tracks new modules) into the package.
# Also copies scripts/clerk.py and the source SKILL.md into the package layout.
vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p "{{VENDOR_DST}}"
    # Copy all Python modules from src/clerk/ — glob auto-tracks new files.
    cp {{VENDOR_SRC}}/*.py "{{VENDOR_DST}}/"
    # Copy the bundled entrypoint.
    cp scripts/clerk.py packages/clerk/.apm/skills/clerk/scripts/
    # Copy the skill definition.
    cp skills/clerk/SKILL.md packages/clerk/.apm/skills/clerk/
    echo "vendor: copied src/clerk/*.py → {{VENDOR_DST}}/"

# Check that the vendored copy in packages/ matches src/clerk/ — fail on drift.
# Run this in CI and before apm pack to catch stale vendored code.
check-vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    TDST="$TMP/clerk"
    mkdir -p "$TDST"
    cp {{VENDOR_SRC}}/*.py "$TDST/"
    # Compare — diff exits non-zero if files differ.
    if ! diff -rq "$TDST/" "{{VENDOR_DST}}/"; then
        echo "check-vendor FAILED: vendored copy differs from src/clerk/." >&2
        echo "Run 'just vendor' to regenerate." >&2
        exit 1
    fi
    echo "check-vendor: ok — vendored copy matches src/clerk/"

# Build both Claude and Codex marketplace artifacts.
# Always re-vendors first (BLOCKER-2: --check-clean does not cover vendored files).
pack: vendor check-vendor
    apm pack --marketplace=claude,codex

# Dry-run pack (no files written, but validates config + prints output paths).
pack-dry: vendor check-vendor
    apm pack --marketplace=claude,codex --dry-run

# Gated release sequence — catches version/tree drift before publishing.
# apm publish is documented but deferred pending the registries feature (Q-008b).
release: vendor check-vendor
    apm pack --marketplace=claude,codex --check-versions --check-clean
    @echo "release: manifests up to date. To publish (when registries feature is adopted):"
    @echo "  apm publish --package copier-clerk/clerk"
