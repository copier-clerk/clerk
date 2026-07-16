"""spec 009 US3 / SC-003 (T026, T027): [base, python] reproduces faithfully.

Generate [base, python], then reproduce onto the same tree and assert:
- T026: the reproduce order is recomputed from the committed answers + pinned
  edges (base before python), not a frozen recipe.
- T027: trust-gated tasks (git init, stubbed gitnr .gitignore, stubbed gh
  LICENSE) RE-RUN under trust at reproduce and are idempotent (their guards
  hold); task outputs are process-deterministic, not asserted byte-identical.

Tasks are the hermetic offline stubs (bailiff_mod_base / bailiff_mod_python
fixtures); the real gitnr/gh tasks re-run identically under the same guards.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import TemplateRepo

# Managed files whose bytes must be stable across reproduce (fresh render of
# base+python onto the already-generated tree). AGENTS.md and pyproject.toml are
# seed-once: on this already-populated tree _skip_if_exists leaves them as-is, so
# their bytes are trivially stable too (asserted in test_seed_once for edits).
_MANAGED_PATHS = [
    "docs/.gitkeep",
    "docs/architecture/.gitkeep",
    "tests/.gitkeep",
    "AGENTS.md",
    "pyproject.toml",
    ".copier-answers.bailiff-mod-base.yml",
    ".copier-answers.bailiff-mod-python.yml",
]


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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _init_base_python(base: TemplateRepo, python: TemplateRepo, dest: Path) -> None:
    trust.add_trust(base.url)
    trust.add_trust(python.url)
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", base, ["project_name", "license", "layout"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["ghg:macOS", "gh:Python"],
            },
        ),
        (
            _record("demo/bailiff-mod-python", python, ["project_name", "python_version"]),
            {"python_version": "3.12"},
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")


def test_reproduce_order_recomputed_from_committed_answers(
    bailiff_mod_base: TemplateRepo, bailiff_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """T026: reproduce order is recomputed (base before python) from committed answers + edges."""
    dest = tmp_path / "proj"
    _init_base_python(bailiff_mod_base, bailiff_mod_python, dest)

    # Sanity: all managed paths actually rendered.
    for p in _MANAGED_PATHS:
        assert (dest / p).is_file(), f"expected managed file {p} to exist after init"

    # Reproduce order is recomputed from committed answers + pinned edges, not a
    # frozen recipe: rebuild the plan from the committed answers files and assert
    # base sorts before python (the run_after edge). reproduce() itself does not
    # leak the recorded source in its RunResult, so we verify order at the planner.
    from bailiff import discovery, ordering

    edges_by_basename: dict[str, dict[str, Any]] = {}
    recs: list[TemplateRecord] = []
    for af in ("bailiff-mod-base", "bailiff-mod-python"):
        import yaml

        raw = yaml.safe_load((dest / f".copier-answers.{af}.yml").read_text())
        disc = discovery.discover(str(raw["_src_path"]), str(raw["_commit"]))
        edges_by_basename[af] = disc.dependency_edges
        recs.append(
            TemplateRecord(
                full_id=f"_recorded/{af}",
                source=str(raw["_src_path"]),
                ref=str(raw["_commit"]),
                versions=disc.versions,
                reproducible=disc.reproducible,
                has_tasks=disc.has_tasks,
                questions=[q.key for q in disc.questions],
            )
        )
    plan = ordering.layer_plan_from_edges(recs, edges_by_basename)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    assert order == ["bailiff-mod-base", "bailiff-mod-python"], f"recomputed order wrong: {order}"

    # reproduce completes without error on the recomputed plan.
    runner.reproduce_many(str(dest))


def test_tasks_rerun_idempotently_on_reproduce(
    bailiff_mod_base: TemplateRepo, bailiff_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """T027: trust-gated tasks re-run under trust and are idempotent (guards hold)."""
    dest = tmp_path / "proj"
    _init_base_python(bailiff_mod_base, bailiff_mod_python, dest)

    # Task outputs present after init.
    assert (dest / ".gitignore").is_file()
    assert (dest / "LICENSE").is_file()
    assert (dest / ".git").is_dir()

    gitignore_before = _digest(dest / ".gitignore")
    license_before = _digest(dest / "LICENSE")

    # Reproduce re-runs tasks; the test -f guards make them idempotent no-ops.
    runner.reproduce_many(str(dest))

    assert (dest / ".gitignore").is_file(), "gitnr output missing after reproduce"
    assert (dest / "LICENSE").is_file(), "LICENSE missing after reproduce"
    # Idempotent guards → these particular (stub) outputs are unchanged.
    assert _digest(dest / ".gitignore") == gitignore_before
    assert _digest(dest / "LICENSE") == license_before
