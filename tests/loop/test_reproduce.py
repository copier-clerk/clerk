"""US2: faithful, agent-free reproduce (SC-001, SC-002, FR-015, FR-015a, FR-017, FR-018)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clerk import runner, trust
from tests.conftest import TemplateRepo

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "clerk.py"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _tree_digest(root: Path, *, include_git: bool = False) -> dict[str, str]:
    """Hash of every rendered file, keyed by relative path.

    The enumerated comparison set (SC-002): all files under the project EXCEPT the
    `.git` working metadata (which is the task's side effect, not rendered output).
    The exclusion allowlist is exactly `.git/**` and nothing else.
    """
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if not include_git and rel.parts and rel.parts[0] == ".git":
            continue
        digests[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def _init(base_template: TemplateRepo, dest: Path) -> None:
    trust.add_trust(base_template.url)
    spec = runner.RunSpec(
        source=base_template.url, dest=str(dest), answers={"project_name": "demo"}
    )
    runner.init(spec, today="2026-07-09")


# ---------------------------------------------------------------------------
# Direct-import tests (unit-level driver guarantees, 001-preserved)
# ---------------------------------------------------------------------------


def test_reproduce_is_byte_identical(base_template: TemplateRepo, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    _init(base_template, dest)
    before = _tree_digest(dest)

    runner.reproduce(str(dest))
    after = _tree_digest(dest)

    # byte-identical over the enumerated set, empty exclusion beyond .git metadata
    assert before == after


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
    from clerk.errors import ClerkError

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ClerkError, match="nothing to reproduce"):
        runner.reproduce(str(empty))


# ---------------------------------------------------------------------------
# SC-002: no clerk artifact in the generated project
# ---------------------------------------------------------------------------


def test_init_writes_no_clerk_file(base_template: TemplateRepo, tmp_path: Path) -> None:
    """init must not write a justfile or any clerk-managed file (FR-002 / SC-002)."""
    dest = tmp_path / "proj"
    _init(base_template, dest)
    assert not (dest / "justfile").exists(), "init must not write a justfile"
    assert not (dest / "Justfile").exists()
    # no clerk.py artifact in the project either
    clerk_artifacts = list(dest.rglob("clerk.py"))
    assert not clerk_artifacts, f"unexpected clerk files in project: {clerk_artifacts}"


# ---------------------------------------------------------------------------
# T011 (a): reproduce via scripts/clerk.py (subprocess)
# ---------------------------------------------------------------------------


def test_reproduce_via_clerk_script(
    base_template: TemplateRepo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scripts/clerk.py reproduce is byte-identical to a direct runner.reproduce call."""
    dest = tmp_path / "proj"
    _init(base_template, dest)
    before = _tree_digest(dest)

    # corrupt a rendered file to confirm reproduce fixes it
    (dest / "out.txt").write_text("CORRUPTED\n")

    settings_path = tmp_path / "settings.yml"
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "reproduce", str(dest)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)},
    )
    assert result.returncode == 0, (
        f"clerk.py reproduce failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    after = _tree_digest(dest)
    assert before == after


# ---------------------------------------------------------------------------
# T011 (b) / T012: copier-only-by-hand reproduce (no clerk, no just)
# ---------------------------------------------------------------------------


def test_copier_only_reproduce_byte_identical(base_template: TemplateRepo, tmp_path: Path) -> None:
    """The copier-only fallback produces the same output as clerk.py reproduce (SC-001).

    Uses `copier recopy --vcs-ref=:current: --defaults --overwrite` directly —
    no clerk import, no just — proving reproduce needs neither clerk nor just installed.
    The assertion is on byte-identical digests vs the recorded commit state.
    """
    # init via the library to get a well-known starting state
    dest_a = tmp_path / "proj_a"
    _init(base_template, dest_a)
    before = _tree_digest(dest_a)

    # Produce a second independent clone via clerk.py, then compare
    # the copier-only recopy path against it.
    dest_b = tmp_path / "proj_b"
    _init(base_template, dest_b)

    # corrupt proj_b; restore via copier-only path (no clerk module involved)
    (dest_b / "out.txt").write_text("HAND EDITED\n")

    settings_path = tmp_path / "settings.yml"
    result = subprocess.run(
        ["copier", "recopy", "--vcs-ref=:current:", "--defaults", "--overwrite"],
        cwd=str(dest_b),
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)},
    )
    assert result.returncode == 0, (
        f"copier recopy failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    after_b = _tree_digest(dest_b)

    # Both trees must be byte-identical (SC-001)
    assert before == after_b, (
        "copier-only reproduce diverges from clerk.py reproduce:\n"
        f"  missing in copier-only: {set(before) - set(after_b)}\n"
        f"  extra in copier-only: {set(after_b) - set(before)}\n"
        f"  changed: {[k for k in before if k in after_b and before[k] != after_b[k]]}"
    )

    # SC-002: no justfile / no clerk artifact in the project
    assert not (dest_b / "justfile").exists()
    assert not (dest_b / "Justfile").exists()


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
# T011: clerk.py reproduce exit code when no answers file
# ---------------------------------------------------------------------------


def test_clerk_script_reproduce_exits_1_no_answers(tmp_path: Path) -> None:
    """scripts/clerk.py reproduce exits 1 when there is nothing to reproduce."""
    empty = tmp_path / "empty"
    empty.mkdir()
    import os

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "reproduce", str(empty)],
        capture_output=True,
        text=True,
        env={**os.environ, "COPIER_SETTINGS_PATH": str(tmp_path / "settings.yml")},
    )
    assert result.returncode == 1
    assert "nothing to reproduce" in result.stderr


# ---------------------------------------------------------------------------
# Reproduce run-spec via JSON (for cross-verification)
# ---------------------------------------------------------------------------


def test_reproduce_via_clerk_script_run_spec_json(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    """scripts/clerk.py init --run-spec then reproduce round-trips byte-identically."""
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

    # init via clerk.py script
    r_init = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_init.returncode == 0, f"init failed:\nstdout: {r_init.stdout}\nstderr: {r_init.stderr}"

    before = _tree_digest(dest)

    # corrupt and reproduce
    (dest / "out.txt").write_text("CORRUPTED\n")
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
