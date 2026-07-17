"""spec 014 T049 / SC-001: bailiff-mod-quality renders correctly.

Init bailiff-mod-quality and assert:
- Non-empty quality_languages → .agents/hooks/quality-languages written with
  sorted-unique tokens, one per line (SC-001, MANAGED lifecycle);
- Duplicate inputs are deduped and sorted before writing;
- Empty quality_languages → .agents/hooks/quality-languages NOT written (SC-001);
- .gitignore.d/bailiff-mod-quality fragment always rendered (FR-013);
- depends_on/phase (when:false) absent from answers file (FR-019).

Pure render module: no tasks to stub. The fixture copies the real template tree.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bailiff import runner, trust
from tests.conftest import (
    _MODULES_DIR,
    TemplateRepo,
    _git,
)


def _copy_quality_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-quality tree into a hermetic tagged git repo.

    No tasks to stub — pure render module. The full copier.yml is used verbatim.
    """
    src = _MODULES_DIR / "bailiff-mod-quality"
    dest_root = tmp_path / "bailiff-mod-quality"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_quality(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-quality template as a hermetic repo (pure render, no tasks)."""
    return _copy_quality_module(tmp_path)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    """Init quality standalone (no base) — used for render-only tests."""
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


_QUALITY_FILE = Path(".agents/hooks/quality-languages")


def test_quality_renders_sorted_unique(bailiff_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """SC-001: quality_languages rendered as sorted-unique tokens, one per line."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_quality, dest, {"quality_languages": ["typescript", "python", "go"]})

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file(), ".agents/hooks/quality-languages not written"
    lines = quality_file.read_text().splitlines()
    # Sorted alphabetically, no empty lines.
    assert lines == ["go", "python", "typescript"], f"unexpected content: {lines}"


def test_quality_deduplicates_inputs(bailiff_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """Duplicate tokens in quality_languages are deduplicated and sorted."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_quality, dest, {"quality_languages": ["python", "python", "go", "go"]})

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file(), ".agents/hooks/quality-languages not written"
    lines = quality_file.read_text().splitlines()
    assert lines == ["go", "python"], f"dedup failed: {lines}"


def test_quality_empty_list_no_file(bailiff_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """Empty quality_languages → .agents/hooks/quality-languages NOT written (never empty file)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_quality, dest, {"quality_languages": []})

    # The directory itself should not exist when the list is empty.
    assert not (dest / ".agents" / "hooks" / "quality-languages").exists(), (
        "quality-languages written for empty list"
    )


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


def test_quality_single_language(bailiff_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """Single-element list renders correctly."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_quality, dest, {"quality_languages": ["python"]})

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file()
    lines = quality_file.read_text().splitlines()
    assert lines == ["python"]


def test_quality_gitignore_fragment_rendered(
    bailiff_mod_quality: TemplateRepo, tmp_path: Path
) -> None:
    """FR-013: .gitignore.d/bailiff-mod-quality fragment is always rendered."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_quality, dest, {"quality_languages": []})

    frag = dest / ".gitignore.d" / "bailiff-mod-quality"
    assert frag.is_file(), ".gitignore.d/bailiff-mod-quality not rendered"
    assert frag.read_text().strip(), "gitignore fragment must not be empty"


def test_quality_answers_recorded(bailiff_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """quality_languages is persisted to the recorded answers file; hidden edges are not."""
    import yaml

    dest = tmp_path / "proj"
    _init(bailiff_mod_quality, dest, {"quality_languages": ["python", "go"]})

    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert af["quality_languages"] == ["python", "go"], "quality_languages not in answers"
    # Hidden ordering edges must NOT appear in answers (spec 014 FR-019).
    assert "run_after" not in af, "stale run_after must not be recorded"
    assert "run_before" not in af, "stale run_before must not be recorded"
    assert "depends_on" not in af, "depends_on (when:false) must not be recorded"
    assert "phase" not in af, "phase (when:false) must not be recorded"
