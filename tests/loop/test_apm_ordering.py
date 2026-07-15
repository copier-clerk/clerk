"""spec 007 SC-005, Q5 (T014): [stub_base, bailiff-mod-apm] composes as a layer.

A [stub_base, bailiff-mod-apm] selection:
- applies base first and threads project_name into the rendered apm.yml (SC-005);
- reproduce_many recomputes the SAME order from committed state (spec-003 engine);
- commits NO bailiff-specific recipe file to the project (spec-010 invariant).

007 declares no hardcoded base (Q5): bailiff-mod-apm's edges are empty, so ordering
here is driven by the STUB BASE declaring run_before: [bailiff-mod-apm] (see the
apm_stub_base fixture) — proving the engine sequences apm after whatever base is
present, without 007 baking it in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import ordering, runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import TemplateRepo

_PKGS = ["srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0"]


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


def _selection(
    apm_stub_base: TemplateRepo, bailiff_mod_apm: TemplateRepo
) -> list[tuple[TemplateRecord, dict[str, Any]]]:
    # Mis-order the selection (apm first) — the base's run_before edge must reorder it.
    return [
        (
            _record("demo/bailiff-mod-apm", bailiff_mod_apm, ["project_name", "apm_packages"]),
            {"apm_packages": _PKGS},
        ),
        (
            _record("demo/bailiff-mod-stub-base", apm_stub_base, ["project_name"]),
            {"project_name": "myapp"},
        ),
    ]


def test_stub_base_orders_before_apm_and_threads(
    apm_stub_base: TemplateRepo, bailiff_mod_apm: TemplateRepo, tmp_path: Path
) -> None:
    """SC-005: base first (from the base's run_before edge); project_name threads."""
    trust.add_trust(apm_stub_base.url)
    trust.add_trust(bailiff_mod_apm.url)
    dest = tmp_path / "proj"
    runner.init_many(_selection(apm_stub_base, bailiff_mod_apm), str(dest), today="2026-07-13")

    # base rendered; apm rendered with the threaded project_name.
    assert (dest / "base_out.txt").read_text() == "base=myapp\n"
    assert yaml.safe_load((dest / "apm.yml").read_text())["name"] == "myapp", (
        "project_name not threaded stub_base → apm"
    )

    # Each layer committed its own answers file; NO bailiff-specific recipe file exists.
    assert (dest / ".copier-answers.bailiff-mod-stub-base.yml").is_file()
    assert (dest / ".copier-answers.bailiff-mod-apm.yml").is_file()
    # spec-010 invariant: no bailiff-authored order/recipe file in the project.
    recipe_like = [
        p.name
        for p in dest.iterdir()
        if p.name.startswith(".bailiff") and p.name.endswith((".yml", ".yaml", ".json"))
    ]
    assert recipe_like == [], f"unexpected bailiff recipe file committed: {recipe_like}"


def test_reproduce_recomputes_same_order(
    apm_stub_base: TemplateRepo, bailiff_mod_apm: TemplateRepo, tmp_path: Path
) -> None:
    """SC-005 / Q5: reproduce recomputes base-before-apm from committed edges."""
    trust.add_trust(apm_stub_base.url)
    trust.add_trust(bailiff_mod_apm.url)
    dest = tmp_path / "proj"
    runner.init_many(_selection(apm_stub_base, bailiff_mod_apm), str(dest), today="2026-07-13")

    # Recompute the order from committed answers + pinned edges (as reproduce does).
    from bailiff import discovery

    edges_by_basename: dict[str, dict[str, Any]] = {}
    recs: list[TemplateRecord] = []
    for af in ("bailiff-mod-stub-base", "bailiff-mod-apm"):
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
    assert order == ["bailiff-mod-stub-base", "bailiff-mod-apm"], f"recomputed order wrong: {order}"

    # And reproduce actually runs clean.
    runner.reproduce_many(str(dest))
    assert (dest / "apm.yml").is_file()
