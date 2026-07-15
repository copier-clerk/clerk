"""US4: consent before an action-taking template runs (FR-019, FR-020, FR-023)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bailiff import runner, trust
from bailiff.errors import UntrustedSourceError
from tests.conftest import TemplateRepo

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bailiff.py"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# Direct-import tests (001-preserved library-level guarantees)
# ---------------------------------------------------------------------------


def test_untrusted_action_template_is_refused(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={"project_name": "x"})

    with pytest.raises(UntrustedSourceError) as excinfo:
        runner.init(spec, today="2026-07-09")

    # names a prefix to trust, and takes no destructive action
    assert excinfo.value.prefix
    assert not dest.exists() or not (dest / "out.txt").exists()


def test_consent_then_success(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={"project_name": "x"})

    # explicit consent step records trust...
    assert trust.add_trust(base_template.url) is True
    # ...then the same generation succeeds
    runner.init(spec, today="2026-07-09")
    assert (dest / "out.txt").exists()


def test_core_never_writes_trust(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={"project_name": "x"})
    with pytest.raises(UntrustedSourceError):
        runner.init(spec, today="2026-07-09")
    # the failed run must NOT have recorded trust on its own (FR-019)
    assert trust.list_trust() == []


# ---------------------------------------------------------------------------
# T016: scripts/bailiff.py trust / init invocation
# ---------------------------------------------------------------------------


def test_bailiff_script_untrusted_exits_3(base_template: TemplateRepo, tmp_path: Path) -> None:
    """scripts/bailiff.py init exits 3 for an untrusted action-taking source."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {"source": base_template.url, "dest": str(dest), "answers": {"project_name": "x"}}
        )
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 3
    # error is on stderr, not a bare stack trace
    assert result.stderr.strip()
    assert not (dest / "out.txt").exists() if dest.exists() else True


def test_bailiff_script_trust_add_from_source_then_init_succeeds(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    """trust add --from-source records consent; subsequent init exits 0 (FR-019/FR-020)."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    # Step 1: trust add --from-source computes and records the prefix
    r_trust = subprocess.run(
        [sys.executable, str(_SCRIPT), "trust", "add", "--from-source", base_template.url],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_trust.returncode == 0, f"trust add failed: {r_trust.stderr}"
    assert "added" in r_trust.stdout or "already trusted" in r_trust.stdout

    # Step 2: init now succeeds
    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {"source": base_template.url, "dest": str(dest), "answers": {"project_name": "x"}}
        )
    )

    r_init = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_init.returncode == 0, (
        f"init after trust failed:\nstdout: {r_init.stdout}\nstderr: {r_init.stderr}"
    )
    assert (dest / "out.txt").exists()


def test_bailiff_script_trust_add_explicit_prefix(tmp_path: Path) -> None:
    """trust add <prefix> records the given prefix; trust list shows it."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    prefix = "https://github.com/bailiff-io/"

    r_add = subprocess.run(
        [sys.executable, str(_SCRIPT), "trust", "add", prefix],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_add.returncode == 0
    assert "added" in r_add.stdout

    r_list = subprocess.run(
        [sys.executable, str(_SCRIPT), "trust", "list"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_list.returncode == 0
    assert prefix in r_list.stdout


def test_bailiff_script_trust_add_idempotent(tmp_path: Path) -> None:
    """trust add a second time prints 'already trusted' and exits 0."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    prefix = "https://github.com/bailiff-io/"

    subprocess.run(
        [sys.executable, str(_SCRIPT), "trust", "add", prefix],
        capture_output=True,
        env=env,
    )
    r2 = subprocess.run(
        [sys.executable, str(_SCRIPT), "trust", "add", prefix],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r2.returncode == 0
    assert "already trusted" in r2.stdout
