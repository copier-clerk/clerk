"""T022 / US2 — the single LIVE-network smoke test (SC-007).

Every other test in the suite is hermetic: it fetches from a throwaway *local*
git repo, so the suite runs offline. This one test proves the same loop works
against a real *remote* source over the network — the one thing local fixtures
cannot cover (an actual `git clone` of a published repo, real tag resolution).

It is marked ``network`` and DESELECTED by default (see ``pyproject.toml``
``addopts = -m 'not network'``). Run it explicitly:

    uv run pytest -m network

Target repo: the hand-published ``bailiff-template-example``. Override with
``BAILIFF_SMOKE_TEMPLATE_URL`` to point at any published bailiff-shaped template
(e.g. a fork, or the monorepo-fanned-out mirror). If the URL is unreachable
(e.g. the repo is not published yet), the test SKIPS rather than fails, so it is
safe to keep in the tree before first publish and starts exercising the moment
the repo goes live.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bailiff import discovery, runner, trust

pytestmark = pytest.mark.network

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bailiff.py"

# The intended first-party published exemplar. A public repo, so no auth needed
# for a read-only clone. Overridable for forks / mirrors.
DEFAULT_TEMPLATE_URL = "https://github.com/bailiff-io/bailiff-template-example.git"
TEMPLATE_URL = os.environ.get("BAILIFF_SMOKE_TEMPLATE_URL", DEFAULT_TEMPLATE_URL)


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
            "(unpublished, offline, or private); set BAILIFF_SMOKE_TEMPLATE_URL to override"
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
            "project_name": "bailiff-smoke",
            "org": "bailiff-io",
            "license": "MIT",
            "description": "live-network smoke test project",
        },
    )
    runner.init(spec, today="2026-07-10")

    # the source + a real resolved version are recorded for reproduce
    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["_src_path"] == url
    assert answers["_commit"] in desc.versions
    assert answers["project_name"] == "bailiff-smoke"

    # 3) reproduce — corrupt, then replay; must come back byte-identical.
    before = _tree_digest(dest)
    (dest / "README.md").write_text("CORRUPTED\n")
    runner.reproduce(str(dest))
    after = _tree_digest(dest)
    assert before == after


def test_live_reproduce_via_bailiff_script(_require_remote: str, tmp_path: Path) -> None:
    """scripts/bailiff.py discover/trust/init/reproduce against the live remote."""
    url = _require_remote
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    # 1) discover via script
    r_discover = subprocess.run(
        [sys.executable, str(_SCRIPT), "discover", url],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_discover.returncode == 0, f"discover failed: {r_discover.stderr}"
    payload = json.loads(r_discover.stdout)
    assert payload["reproducible"] is True
    assert payload["versions"]

    # 2) trust add --from-source
    r_trust = subprocess.run(
        [sys.executable, str(_SCRIPT), "trust", "add", "--from-source", url],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_trust.returncode == 0, f"trust add failed: {r_trust.stderr}"

    # 3) init via script
    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {
                "source": url,
                "dest": str(dest),
                "answers": {
                    "project_name": "bailiff-smoke",
                    "org": "bailiff-io",
                    "license": "MIT",
                    "description": "live-network smoke via script",
                },
            }
        )
    )
    r_init = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_init.returncode == 0, f"init failed:\nstdout: {r_init.stdout}\nstderr: {r_init.stderr}"

    before = _tree_digest(dest)

    # SC-002: no bailiff artifact
    assert not (dest / "justfile").exists()
    assert not (dest / "Justfile").exists()

    # 4) corrupt and reproduce via script
    (dest / "README.md").write_text("CORRUPTED\n")
    r_repro = subprocess.run(
        [sys.executable, str(_SCRIPT), "reproduce", str(dest)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_repro.returncode == 0, (
        f"reproduce failed:\nstdout: {r_repro.stdout}\nstderr: {r_repro.stderr}"
    )
    after = _tree_digest(dest)
    assert before == after


def test_live_copier_only_reproduce_byte_identical(_require_remote: str, tmp_path: Path) -> None:
    """copier-only-by-hand reproduce matches bailiff.py reproduce against the live remote.

    Proves the US1 fallback: `copier recopy --vcs-ref=:current: --defaults --overwrite`
    in the project dir needs no bailiff on PATH (FR-003 / SC-001).
    """
    url = _require_remote
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    trust.add_trust(url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=url,
        dest=str(dest),
        answers={
            "project_name": "bailiff-smoke",
            "org": "bailiff-io",
            "license": "MIT",
            "description": "copier-only fallback test",
        },
    )
    runner.init(spec, today="2026-07-10")
    before = _tree_digest(dest)

    # corrupt and restore via the copier-only path (no bailiff module used here)
    (dest / "README.md").write_text("CORRUPTED\n")
    result = subprocess.run(
        ["copier", "recopy", "--vcs-ref=:current:", "--defaults", "--overwrite"],
        cwd=str(dest),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"copier recopy failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    after = _tree_digest(dest)
    assert before == after, (
        "copier-only reproduce diverges from the recorded state:\n"
        f"  changed: {[k for k in before if k in after and before[k] != after[k]]}"
    )
