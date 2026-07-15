"""US4: merge conflict detection — exit 4, conflicted paths named.

SC-004, FR-007 (spec 006).

Phase 0 / T002 finding: copier's run_update does NOT raise on conflict.
In inline mode it writes ``<<<<<<< before updating`` markers.
In rej mode it writes ``.rej`` files.
bailiff detects both post-update.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bailiff import runner
from bailiff.errors import MergeConflictError
from tests.conftest import ConflictUpgradeFixture

_PATH = __import__("os").environ.get("PATH", "/usr/bin:/bin")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "bailiff-test",
            "GIT_AUTHOR_EMAIL": "test@bailiff.invalid",
            "GIT_COMMITTER_NAME": "bailiff-test",
            "GIT_COMMITTER_EMAIL": "test@bailiff.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": _PATH,
        },
    )


def _setup_conflict_project(source_url: str, dest: Path) -> Path:
    """Init v1.0.0, locally edit hello.txt, commit — setting up the conflict scenario.

    v1.0.0 renders hello.txt = "line1"; v1.1.0 changes it to "changed_line1".
    We overwrite hello.txt with "local_edit" before committing, so the 3-way
    merge of (old="line1", new="changed_line1", local="local_edit") will conflict.
    """
    from copier import run_copy

    dest.mkdir(parents=True, exist_ok=True)
    run_copy(
        source_url,
        str(dest),
        data={"project_name": "myproject"},
        vcs_ref="v1.0.0",
        defaults=True,
        overwrite=True,
        quiet=True,
    )
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-qm", "initial")

    # Apply local edit AFTER the initial commit so it diverges from v1.0.0
    (dest / "hello.txt").write_text("local_edit\n")
    _git(dest, "add", "hello.txt")
    _git(dest, "commit", "-qm", "local edit")

    # copier uses the default answers file name when no explicit answers_file is given
    af_candidates = sorted(dest.glob(".copier-answers*.yml"))
    assert af_candidates, "no .copier-answers*.yml found after init"
    return af_candidates[0]


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_inline_conflict_raises_merge_conflict_error(
    conflict_upgrade_fixture: ConflictUpgradeFixture, tmp_path: Path
) -> None:
    """US4-AS1: inline conflict → MergeConflictError; hello.txt named; markers present."""
    dest = tmp_path / "proj"
    source_url = str(conflict_upgrade_fixture.repo_path)
    af = _setup_conflict_project(source_url, dest)

    with pytest.raises(MergeConflictError) as exc_info:
        runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0", conflict="inline")

    err = exc_info.value
    assert "hello.txt" in err.conflicted_paths
    # Inline conflict markers should be present in the file
    content = (dest / "hello.txt").read_bytes()
    assert b"<<<<<<< " in content


def test_rej_conflict_raises_merge_conflict_error(
    conflict_upgrade_fixture: ConflictUpgradeFixture, tmp_path: Path
) -> None:
    """US4-AS2: rej mode → MergeConflictError; .rej file present."""
    dest = tmp_path / "proj"
    source_url = str(conflict_upgrade_fixture.repo_path)
    af = _setup_conflict_project(source_url, dest)

    with pytest.raises(MergeConflictError) as exc_info:
        runner.update(dest=str(dest), answers_file=af, vcs_ref="v1.1.0", conflict="rej")

    err = exc_info.value
    # In rej mode, the conflicted path is the .rej file
    assert any(".rej" in p for p in err.conflicted_paths)
