"""spec 011 §quality / SC-001, SC-002 (T010): clerk-mod-quality renders correctly.

Init clerk-mod-quality and assert:
- Non-empty quality_languages → .agents/hooks/quality-languages written with
  sorted-unique tokens, one per line (SC-001, MANAGED lifecycle);
- Duplicate inputs are deduped and sorted before writing;
- Empty quality_languages → .agents/hooks/quality-languages NOT written (SC-001);
- MANAGED file is byte-identical on reproduce (SC-002, Constitution III).

Pure render module: no tasks to stub. The fixture copies the real template tree.
The reproduce test pairs with clerk-mod-base (run_after edge) because reproduce_many
recomputes the plan from committed edges and refuses a dangling run_after reference.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest

from clerk import runner, trust
from clerk.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _MODULES_DIR,
    TemplateRepo,
    _copy_module_with_stub_tasks,
    _git,
)


def _copy_quality_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real clerk-mod-quality tree into a hermetic tagged git repo.

    No tasks to stub — pure render module. The full copier.yml is used verbatim.
    """
    src = _MODULES_DIR / "clerk-mod-quality"
    dest_root = tmp_path / "clerk-mod-quality"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def clerk_mod_quality(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-quality template as a hermetic repo (pure render, no tasks)."""
    return _copy_quality_module(tmp_path)


@pytest.fixture
def clerk_mod_base(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-base template as a hermetic repo (tasks stubbed offline)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-base", tmp_path / "clerk-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=questions,
    )


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    """Init quality standalone (no base) — used for render-only tests."""
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


def _init_with_base(
    base: TemplateRepo,
    quality: TemplateRepo,
    dest: Path,
    quality_languages: list[str],
) -> None:
    """Init [base, quality] together — required for reproduce tests (run_after edge)."""
    trust.add_trust(base.url)
    trust.add_trust(quality.url)
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", base, ["project_name"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/clerk-mod-quality", quality, ["quality_languages"]),
            {"quality_languages": quality_languages},
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-14")


_QUALITY_FILE = Path(".agents/hooks/quality-languages")


def test_quality_renders_sorted_unique(clerk_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """SC-001: quality_languages rendered as sorted-unique tokens, one per line."""
    dest = tmp_path / "proj"
    _init(clerk_mod_quality, dest, {"quality_languages": ["typescript", "python", "go"]})

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file(), ".agents/hooks/quality-languages not written"
    lines = quality_file.read_text().splitlines()
    # Sorted alphabetically, no empty lines.
    assert lines == ["go", "python", "typescript"], f"unexpected content: {lines}"


def test_quality_deduplicates_inputs(clerk_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """Duplicate tokens in quality_languages are deduplicated and sorted."""
    dest = tmp_path / "proj"
    _init(clerk_mod_quality, dest, {"quality_languages": ["python", "python", "go", "go"]})

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file(), ".agents/hooks/quality-languages not written"
    lines = quality_file.read_text().splitlines()
    assert lines == ["go", "python"], f"dedup failed: {lines}"


def test_quality_empty_list_no_file(clerk_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """Empty quality_languages → .agents/hooks/quality-languages NOT written (never empty file)."""
    dest = tmp_path / "proj"
    _init(clerk_mod_quality, dest, {"quality_languages": []})

    # The directory itself should not exist when the list is empty.
    assert not (dest / ".agents" / "hooks" / "quality-languages").exists(), (
        "quality-languages written for empty list"
    )


def test_quality_managed_byte_identical_on_reproduce(
    clerk_mod_base: TemplateRepo,
    clerk_mod_quality: TemplateRepo,
    tmp_path: Path,
) -> None:
    """SC-002: MANAGED file byte-identical on reproduce (Constitution III).

    Pairs with clerk-mod-base because reproduce_many recomputes the DAG from
    committed answers + edges, and the run_after: [clerk-mod-base] edge would
    be dangling if base were absent from the project.
    """
    dest = tmp_path / "proj"
    _init_with_base(clerk_mod_base, clerk_mod_quality, dest, ["rust", "python"])

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file(), ".agents/hooks/quality-languages not present after init"
    before = _digest(quality_file)
    answers_before = _digest(dest / ".copier-answers.clerk-mod-quality.yml")

    runner.reproduce_many(str(dest))

    # MANAGED: byte-identical after reproduce.
    assert _digest(quality_file) == before, "quality-languages changed on reproduce"
    assert _digest(dest / ".copier-answers.clerk-mod-quality.yml") == answers_before, (
        "answers changed on reproduce"
    )


def test_quality_single_language(clerk_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """Single-element list renders correctly."""
    dest = tmp_path / "proj"
    _init(clerk_mod_quality, dest, {"quality_languages": ["python"]})

    quality_file = dest / _QUALITY_FILE
    assert quality_file.is_file()
    lines = quality_file.read_text().splitlines()
    assert lines == ["python"]


def test_quality_answers_recorded(clerk_mod_quality: TemplateRepo, tmp_path: Path) -> None:
    """quality_languages is persisted to the recorded answers file; hidden edges are not."""
    import yaml

    dest = tmp_path / "proj"
    _init(clerk_mod_quality, dest, {"quality_languages": ["python", "go"]})

    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert af["quality_languages"] == ["python", "go"], "quality_languages not in answers"
    # Hidden ordering edges must NOT appear in answers (FR-004).
    assert "run_after" not in af
    assert "depends_on" not in af
    assert "run_before" not in af
