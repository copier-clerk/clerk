"""T034 / US2 — the single LIVE-network smoke test (SC-007).

Every other test in the suite is hermetic: it fetches from a throwaway *local*
git repo, so the suite runs offline. This one test proves the same loop works
against a real *remote* source over the network — the one thing local fixtures
cannot cover (an actual `git clone` of a published repo, real tag resolution).

It is marked ``network`` and DESELECTED by default (see ``pyproject.toml``
``addopts = -m 'not network'``). Run it explicitly:

    uv run pytest -m network

Target repo: the hand-published ``clerk-template-example``. Override with
``CLERK_SMOKE_TEMPLATE_URL`` to point at any published clerk-shaped template
(e.g. a fork, or the monorepo-fanned-out mirror). If the URL is unreachable
(e.g. the repo is not published yet), the test SKIPS rather than fails, so it is
safe to keep in the tree before first publish and starts exercising the moment
the repo goes live.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from clerk import discovery, runner, trust

pytestmark = pytest.mark.network

# The intended first-party published exemplar. A public repo, so no auth needed
# for a read-only clone. Overridable for forks / mirrors.
DEFAULT_TEMPLATE_URL = "https://github.com/copier-clerk/clerk-template-example.git"
TEMPLATE_URL = os.environ.get("CLERK_SMOKE_TEMPLATE_URL", DEFAULT_TEMPLATE_URL)


def _remote_reachable(url: str) -> bool:
    """True if `git ls-remote` succeeds — i.e. the repo is published and clonable."""
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


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Never touch the developer's real ~/.config trust store.
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


@pytest.fixture(scope="session")
def _require_remote() -> str:
    if not _remote_reachable(TEMPLATE_URL):
        pytest.skip(
            f"live template {TEMPLATE_URL!r} not reachable "
            "(unpublished, offline, or private); set CLERK_SMOKE_TEMPLATE_URL to override"
        )
    return TEMPLATE_URL


def _tree_digest(root: Path) -> dict[str, str]:
    """SHA-256 of every rendered file except `.git` working metadata."""
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] == ".git":
            continue
        digests[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def test_live_discover_init_reproduce(_require_remote: str, tmp_path: Path) -> None:
    """The whole loop against a real remote: discover → init → faithful reproduce."""
    url = _require_remote

    # 1) discover — static parse of the cloned template (no code execution).
    desc = discovery.discover(url, None)
    assert desc.reproducible, "published template must ship its answers-file .jinja"
    assert desc.versions, "published template must carry at least one PEP 440 tag"

    # The action-taking template must be trusted before init runs its tasks.
    trust.add_trust(url)

    # 2) init — generate from the live source at its latest tag.
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=url,
        dest=str(dest),
        answers={
            "project_name": "clerk-smoke",
            "org": "copier-clerk",
            "license": "MIT",
            "description": "live-network smoke test project",
        },
    )
    runner.init(spec, today="2026-07-10")

    # the source + a real resolved version are recorded for reproduce
    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["_src_path"] == url
    assert answers["_commit"] in desc.versions
    assert answers["project_name"] == "clerk-smoke"

    # 3) reproduce — corrupt, then replay; must come back byte-identical.
    before = _tree_digest(dest)
    (dest / "README.md").write_text("CORRUPTED\n")
    runner.reproduce(str(dest))
    after = _tree_digest(dest)
    assert before == after
