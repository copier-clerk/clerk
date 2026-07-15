"""T015: catalog smoke test against the live published template (network-marked).

Marked ``network`` and deselected by default (``pyproject.toml`` addopts =
``-m 'not network'``).  Run explicitly::

    uv run pytest -m network

Points a ``--catalog`` file at ``bailiff-io/bailiff-template-example`` and
asserts ``catalog list`` shows it as usable at ``v1.0.0``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import tomli_w

pytestmark = pytest.mark.network

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bailiff.py"

# The hand-published exemplar; matches what the other smoke test uses.
DEFAULT_TEMPLATE_URL = "https://github.com/bailiff-io/bailiff-template-example.git"
TEMPLATE_URL = os.environ.get("BAILIFF_SMOKE_TEMPLATE_URL", DEFAULT_TEMPLATE_URL)


def _remote_reachable(url: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", url],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.fixture(scope="session")
def _require_remote() -> str:
    if not _remote_reachable(TEMPLATE_URL):
        pytest.skip(
            f"live template {TEMPLATE_URL!r} not reachable "
            "(unpublished, offline, or private); set BAILIFF_SMOKE_TEMPLATE_URL to override"
        )
    return TEMPLATE_URL


def test_catalog_list_shows_remote_template_usable(_require_remote: str, tmp_path: Path) -> None:
    """catalog list --json reports bailiff-template-example as usable at v1.0.0."""
    url = _require_remote
    cat_path = tmp_path / "catalog.toml"
    data = {"catalog": [{"name": "smoke", "sources": [url]}]}
    cat_path.write_bytes(tomli_w.dumps(data).encode())

    env = {**os.environ, "BAILIFF_CATALOG_PATH": str(cat_path)}
    r = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "catalog",
            "--catalog",
            str(cat_path),
            "list",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, f"catalog list failed:\n{r.stderr}"

    payload = json.loads(r.stdout)
    cl = payload["catalogs"][0]
    assert cl["name"] == "smoke"
    assert cl["unusable"] == [], f"template unexpectedly unusable: {cl['unusable']}"

    templates = cl["templates"]
    assert len(templates) == 1
    tmpl = templates[0]
    assert tmpl["full_id"] == "smoke/bailiff-template-example"
    assert tmpl["reproducible"] is True
    assert "v1.0.0" in tmpl["versions"]
