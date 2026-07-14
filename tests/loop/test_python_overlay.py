"""spec 009 US2 #1 / SC-002 (T024): the Python overlay applies after base.

Init [clerk-mod-base, clerk-mod-python] (mis-ordered on input) and assert:
- base renders before python (the run_after edge is honoured);
- project_name is threaded from base into the overlay;
- pyproject.toml is present with the threaded name + pinned requires-python;
- the .gitignore stack (base's single writer) included the python token.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

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


def test_base_python_ordered_and_threaded(
    clerk_mod_base: TemplateRepo, clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """SC-002: [base, python] applies base first, threads project_name, seeds pyproject."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    # Mis-order the selection (python first) — the run_after edge must reorder it.
    # Only base carries project_name; python must inherit it via threading (FR-010).
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-python", clerk_mod_python, ["project_name", "python_version"]),
            {"python_version": "3.12"},
        ),
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                # base owns the single .gitignore writer; python's token is threaded in.
                "gitignore_stack": ["ghg:macOS", "gh:Python"],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")

    # Base rendered: its scaffold + AGENTS.md exist.
    assert (dest / "AGENTS.md").is_file(), "base did not render (AGENTS.md missing)"
    assert (dest / "tests" / ".gitkeep").is_file(), "base dir scaffold missing"

    # Python overlay rendered: pyproject.toml present (seed-once) with threaded name + pin.
    pyproject = (dest / "pyproject.toml").read_text()
    assert 'name = "myapp"' in pyproject, "project_name not threaded base→python"
    assert 'requires-python = ">=3.12"' in pyproject, "python_version not pinned"

    # Each layer committed its own answers file.
    af_base = yaml.safe_load((dest / ".copier-answers.clerk-mod-base.yml").read_text())
    af_py = yaml.safe_load((dest / ".copier-answers.clerk-mod-python.yml").read_text())
    assert clerk_mod_base.url in af_base["_src_path"]
    assert clerk_mod_python.url in af_py["_src_path"]
    # Threaded value landed in the python layer's recorded answers.
    assert af_py["project_name"] == "myapp"
    assert af_py["python_version"] == "3.12"

    # base's single .gitignore writer consumed the stack (python token included).
    gitignore = (dest / ".gitignore").read_text()
    assert "gh:Python" in gitignore, "python token not threaded into base gitignore_stack"

    # python overlay's mise-install sentinel present (init-only guard stub ran).
    # The module writes no .gitignore of its own (single writer — base's task output).
    assert (dest / ".clerk-python-mise-installed").is_file()


def test_ordering_recomputed_edge(
    clerk_mod_base: TemplateRepo, clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """The run_after edge sequences base before python regardless of input order.

    Verified via the layer plan (same DAG init and reproduce use).
    """
    from clerk import ordering

    recs = [
        _record("demo/clerk-mod-python", clerk_mod_python, ["project_name"]),
        _record("demo/clerk-mod-base", clerk_mod_base, ["project_name"]),
    ]
    plan = ordering.layer_plan(recs)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    assert order == ["clerk-mod-base", "clerk-mod-python"], f"edge not honoured: {order}"
