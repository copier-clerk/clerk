"""spec 014 (prev 009 US2 #1 / SC-002 T024): the Python overlay applies after base.

Init [bailiff-mod-base, bailiff-mod-python] (mis-ordered on input) and assert:
- base renders before python (the depends_on edge is honoured);
- project_name is read from base via _external_data;
- pyproject.toml is present with the resolved name + pinned requires-python;
- base's stub gitignore includes a token passed directly to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
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


def test_base_python_ordered_and_external_data(
    bailiff_mod_base: TemplateRepo, bailiff_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """SC-002: [base, python] applies base first, resolves project_name via _external_data."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_python.url)

    dest = tmp_path / "proj"
    # Mis-order the selection (python first) — the depends_on edge must reorder it.
    # base carries project_name; python reads it via _external_data.base (spec 014 FR-004).
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record(
                "demo/bailiff-mod-python", bailiff_mod_python, ["project_name", "python_version"]
            ),
            {"python_version": "3.12"},
        ),
        (
            _record(
                "demo/bailiff-mod-base", bailiff_mod_base, ["project_name", "license", "layout"]
            ),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["ghg:macOS", "gh:Python"],
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")

    # Base rendered: its scaffold + AGENTS.md exist.
    assert (dest / "AGENTS.md").is_file(), "base did not render (AGENTS.md missing)"
    assert (dest / "tests" / ".gitkeep").is_file(), "base dir scaffold missing"

    # Python overlay rendered: pyproject.toml present (seed-once) with resolved name + pin.
    pyproject = (dest / "pyproject.toml").read_text()
    assert 'name = "myapp"' in pyproject, "project_name not resolved from base via _external_data"
    assert 'requires-python = ">=3.12"' in pyproject, "python_version not pinned"

    # Each layer committed its own answers file.
    af_base = yaml.safe_load((dest / ".copier-answers.bailiff-mod-base.yml").read_text())
    af_py = yaml.safe_load((dest / ".copier-answers.bailiff-mod-python.yml").read_text())
    assert bailiff_mod_base.url in af_base["_src_path"]
    assert bailiff_mod_python.url in af_py["_src_path"]
    # _external_data read: python recorded the resolved project_name in its own answers.
    assert af_py["project_name"] == "myapp"
    assert af_py["python_version"] == "3.12"

    # base's stub gitignore is written (spec 014: stub replaces gitnr stack union).
    gitignore = (dest / ".gitignore").read_text()
    assert "stub gitignore" in gitignore, "base stub task did not write .gitignore"

    # python overlay's mise-install sentinel present (init-only guard stub ran).
    assert (dest / ".bailiff-python-mise-installed").is_file()


def test_ordering_recomputed_edge(
    bailiff_mod_base: TemplateRepo, bailiff_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """The depends_on edge sequences base before python regardless of input order.

    Verified via the layer plan (same DAG init and reproduce use).
    """
    from bailiff import ordering

    recs = [
        _record("demo/bailiff-mod-python", bailiff_mod_python, ["project_name"]),
        _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
    ]
    plan = ordering.layer_plan(recs)
    order = [r.full_id.rsplit("/", 1)[-1] for r, _ in plan]
    assert order == ["bailiff-mod-base", "bailiff-mod-python"], f"edge not honoured: {order}"
