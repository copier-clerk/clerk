"""spec 009 US4 #2 / SC-003a (T029): seed-once files are not clobbered on re-run.

Generate [base, python], hand-edit AGENTS.md and pyproject.toml, then re-run
(reproduce over the populated tree) → both edited files are PRESERVED
(_skip_if_exists), while a managed file (a scaffold .gitkeep) is still
re-rendered. This is the re-run/update case D-009-7 protects; on a fresh-checkout
reproduce these files render normally (Constitution III holds — covered by the
init tests).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from clerk import runner, trust
from clerk.catalog import TemplateRecord
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=True,
        questions=questions,
    )


def test_seed_once_files_preserved_managed_rerendered(
    clerk_mod_base: TemplateRepo, clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """AGENTS.md + pyproject.toml preserved on re-run; a scaffold .gitkeep re-rendered."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {"project_name": "myapp", "license": "mit", "layout": "single"},
        ),
        (
            _record("demo/clerk-mod-python", clerk_mod_python, ["project_name", "python_version"]),
            {"python_version": "3.12"},
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")

    # Hand-edit the two seed-once files (simulating project ownership after init).
    agents_edit = "# myapp\n\nHAND-EDITED BY THE PROJECT — do not clobber.\n"
    pyproject_edit = '[project]\nname = "myapp"\ndependencies = ["fastapi"]  # project added this\n'
    (dest / "AGENTS.md").write_text(agents_edit)
    (dest / "pyproject.toml").write_text(pyproject_edit)

    # Also clobber a MANAGED scaffold file to prove it IS re-rendered.
    (dest / ".codex" / ".gitkeep").write_text("CORRUPTED")

    # Re-run over the populated tree.
    runner.reproduce_many(str(dest))

    # Seed-once files: project edits preserved (_skip_if_exists).
    assert (dest / "AGENTS.md").read_text() == agents_edit, "AGENTS.md was clobbered (seed-once)"
    assert (dest / "pyproject.toml").read_text() == pyproject_edit, (
        "pyproject.toml was clobbered (seed-once)"
    )

    # Managed file: re-rendered back to empty (a .gitkeep is always empty).
    assert (dest / ".codex" / ".gitkeep").read_text() == "", (
        "managed .gitkeep was not re-rendered on reproduce"
    )
