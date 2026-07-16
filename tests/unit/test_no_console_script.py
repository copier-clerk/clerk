"""Spec 013 FR-001 / constitution v3.0.0: the console entry point IS the tool.

Inverts the former spec-010 assertions (no console script, bundled script exists):
after ADR-0008 the `bailiff` console entry must exist and `scripts/bailiff.py`
must be gone (FR-006: deleted, no shim).
"""

from __future__ import annotations

import tomllib  # stdlib ≥3.11
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def test_project_scripts_declares_bailiff() -> None:
    """pyproject.toml must declare `[project.scripts] bailiff` (spec 013 FR-001)."""
    data = tomllib.loads(_PYPROJECT.read_text())
    scripts = data.get("project", {}).get("scripts", {})
    assert scripts.get("bailiff") == "bailiff.cli:main", (
        f"[project.scripts] bailiff missing or wrong; found: {scripts}"
    )


def test_bundled_script_is_deleted() -> None:
    """scripts/bailiff.py must NOT exist (FR-006: deleted, no shim)."""
    assert not (_REPO_ROOT / "scripts" / "bailiff.py").exists(), (
        "scripts/bailiff.py still exists — decisions-ledger FR-006 requires deletion"
    )
