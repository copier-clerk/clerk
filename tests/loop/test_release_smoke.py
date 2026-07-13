"""Release/fan-out smoke test (spec 008b / T015).

OFFLINE-verifiable parts of the end-to-end smoke:
  - `scripts/check_modules.py` exits 0 against the real templates/ (contract lint).
  - `scripts/generate_catalog.py` emits valid JSON containing clerk-mod-base +
    clerk-mod-python *when their split-repo tags are present* (mocked here — the
    tag fetch is the only network dependency).

CATALOG-EMPTY-UNTIL-FANOUT: the live generator calls discovery.list_versions()
against copier-clerk/clerk-mod-<name>, which do not exist until the release
workflow's fan-out step first mirrors + tags them. Until then the live catalog
OMITS every module (Q-008b-a "omit modules with no published tags"), so a live
`--dry-run` yields `"modules": []`. The `network`-marked test below documents
and verifies that; the offline test proves the generator is otherwise correct.

NOT COVERED HERE (requires copier-clerk org-admin — see docs/runbooks/fanout-release.md):
  - the live canary release (bump -> push -> fan-out -> catalog -> Pages), and
  - discovery.discover() against a fanned-out clerk-mod-* repo asserting
    reproducible=True + a PEP 440 tag.
Both need the clerk-fanout GitHub App + org secrets + Pages enabled, so they are
skip-marked below rather than faked.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
_TEMPLATES = _REPO_ROOT / "templates"

# The real modules spec 009 landed; the smoke asserts these appear in the catalog.
_EXPECTED_MODULES = {"clerk-mod-base", "clerk-mod-python"}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_check_modules_passes_against_real_templates() -> None:
    """`check-modules` exits 0 against the real templates/ (offline; git tag -l only)."""
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "check_modules.py")],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0, f"check-modules failed:\n{proc.stdout}\n{proc.stderr}"


def test_generate_catalog_emits_real_modules_when_tagged() -> None:
    """Generator emits valid JSON with both real modules once their tags exist.

    Offline: the only network call (list_versions -> git ls-remote) is mocked to
    simulate a post-fan-out world where each split repo has a published tag.
    """
    gc = _load("generate_catalog")
    with patch.object(gc, "list_versions", return_value=["v1.0.0"]):
        catalog = gc.generate_catalog(_TEMPLATES)

    # Round-trips as JSON (shape validity).
    json.loads(json.dumps(catalog))
    assert catalog["version"] == 1
    assert catalog["generated_at"].endswith("Z")
    names = {m["name"] for m in catalog["modules"]}
    assert names >= _EXPECTED_MODULES, f"expected {_EXPECTED_MODULES}, got {names}"
    for mod in catalog["modules"]:
        assert mod["source"].startswith("https://")
        assert mod["latest_version"] == "v1.0.0"


@pytest.mark.network
def test_live_catalog_dry_run_is_valid_but_empty_until_fanout() -> None:
    """Live `--dry-run` is valid JSON; modules is empty until the first fan-out.

    Verifies the documented catalog-empty-until-fanout behaviour: the split repos
    copier-clerk/clerk-mod-* do not exist yet, so every module is omitted.
    """
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "generate_catalog.py"), "--dry-run"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["version"] == 1
    assert "modules" in payload
    # Until fan-out publishes tags, the live catalog omits every module.
    assert payload["modules"] == [], (
        "expected an empty catalog before the first fan-out; "
        f"got {payload['modules']!r} — split repos may now exist"
    )


@pytest.mark.network
def test_fanned_out_repo_is_reproducible() -> None:
    """discovery.discover() against a fanned-out clerk-mod-* repo (post-release).

    Skipped until the clerk-fanout App + org secrets + Pages are set up and a
    canary release has mirrored at least one module (docs/runbooks/fanout-release.md).
    Cannot be faked: it asserts a live split repo is reproducible at a PEP 440 tag.
    """
    pytest.skip(
        "live canary not run: requires copier-clerk org-admin setup "
        "(clerk-fanout App + org secrets + Pages) and a fanned-out clerk-mod-* repo "
        "— see docs/runbooks/fanout-release.md"
    )
