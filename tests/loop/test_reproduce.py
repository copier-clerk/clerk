"""US2: faithful, agent-free reproduce (SC-001, SC-002, FR-015, FR-015a, FR-017, FR-018)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bailiff import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(base_template: TemplateRepo, dest: Path) -> None:
    trust.add_trust(base_template.url)
    spec = runner.RunSpec(
        source=base_template.url, dest=str(dest), answers={"project_name": "demo"}
    )
    runner.init(spec, today="2026-07-09")


# ---------------------------------------------------------------------------
# Direct-import tests (unit-level driver guarantees, 001-preserved)
# ---------------------------------------------------------------------------


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


def test_reproduce_overwrites_local_edits_in_place(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    _init(base_template, dest)

    rendered = dest / "out.txt"
    rendered.write_text("HAND EDITED — should be reverted\n")
    unrelated = dest / "my_notes.md"
    unrelated.write_text("keep me\n")

    runner.reproduce(str(dest))

    # rendered file reverts (FR-015a); unrelated file survives
    assert "HAND EDITED" not in rendered.read_text()
    assert rendered.read_text().strip().startswith("name=demo")
    assert unrelated.exists()


def test_reproduce_requires_answers_file(tmp_path: Path) -> None:
    from bailiff.errors import BailiffError

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(BailiffError, match="nothing to reproduce"):
        runner.reproduce(str(empty))


# ---------------------------------------------------------------------------
# SC-002: no bailiff artifact in the generated project
# ---------------------------------------------------------------------------


def test_init_writes_no_bailiff_file(base_template: TemplateRepo, tmp_path: Path) -> None:
    """init must not write a justfile or any bailiff-managed file (FR-002 / SC-002)."""
    dest = tmp_path / "proj"
    _init(base_template, dest)
    assert not (dest / "justfile").exists(), "init must not write a justfile"
    assert not (dest / "Justfile").exists()
    # no bailiff.py artifact in the project either
    bailiff_artifacts = list(dest.rglob("bailiff.py"))
    assert not bailiff_artifacts, f"unexpected bailiff files in project: {bailiff_artifacts}"


# ---------------------------------------------------------------------------
# T011 (a): reproduce via the bailiff CLI (subprocess)
# ---------------------------------------------------------------------------


def test_reproduce_via_bailiff_script(
    base_template: TemplateRepo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """the bailiff CLI reproduce runs successfully and repairs a corrupted rendered file."""
    dest = tmp_path / "proj"
    _init(base_template, dest)

    # corrupt a rendered file to confirm reproduce fixes it
    (dest / "out.txt").write_text("CORRUPTED\n")

    settings_path = tmp_path / "settings.yml"
    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "reproduce", str(dest)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)},
    )
    assert result.returncode == 0, (
        f"bailiff.py reproduce failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "CORRUPTED" not in (dest / "out.txt").read_text()


# ---------------------------------------------------------------------------
# T011 (b) / T012: copier-only-by-hand reproduce (no bailiff, no just)
# ---------------------------------------------------------------------------


# (copier-only reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# T012: run-spec helper round-trip — prove enumerate_answers_files works
# ---------------------------------------------------------------------------


def test_enumerate_answers_files_finds_default(base_template: TemplateRepo, tmp_path: Path) -> None:
    """enumerate_answers_files returns the single .copier-answers.yml at N=1."""
    dest = tmp_path / "proj"
    _init(base_template, dest)
    files = runner.enumerate_answers_files(str(dest))
    assert len(files) == 1
    assert files[0].name == ".copier-answers.yml"


def test_enumerate_answers_files_empty_dir(tmp_path: Path) -> None:
    """enumerate_answers_files returns [] for a directory with no answers files."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert runner.enumerate_answers_files(str(empty)) == []


# ---------------------------------------------------------------------------
# T011: bailiff.py reproduce exit code when no answers file
# ---------------------------------------------------------------------------


def test_bailiff_script_reproduce_exits_1_no_answers(tmp_path: Path) -> None:
    """the bailiff CLI reproduce exits 1 when there is nothing to reproduce."""
    empty = tmp_path / "empty"
    empty.mkdir()
    import os

    result = subprocess.run(
        [sys.executable, "-m", "bailiff", "reproduce", str(empty)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )
    assert result.returncode == 1
    assert "nothing to reproduce" in result.stderr


# ---------------------------------------------------------------------------
# Reproduce run-spec via JSON (for cross-verification)
# ---------------------------------------------------------------------------


def test_reproduce_via_bailiff_script_run_spec_json(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    """the bailiff CLI init --run-spec then reproduce round-trips (repairs a corrupted file)."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    # Trust the source
    trust.add_trust(base_template.url)

    # Write a run-spec
    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {"source": base_template.url, "dest": str(dest), "answers": {"project_name": "demo"}}
        )
    )

    # init via bailiff.py script
    r_init = subprocess.run(
        [sys.executable, "-m", "bailiff", "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_init.returncode == 0, f"init failed:\nstdout: {r_init.stdout}\nstderr: {r_init.stderr}"

    # corrupt and reproduce
    (dest / "out.txt").write_text("CORRUPTED\n")
    r_repro = subprocess.run(
        [sys.executable, "-m", "bailiff", "reproduce", str(dest)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_repro.returncode == 0, (
        f"reproduce failed:\nstdout: {r_repro.stdout}\nstderr: {r_repro.stderr}"
    )
    assert "CORRUPTED" not in (dest / "out.txt").read_text()
