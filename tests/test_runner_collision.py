"""Unit tests for the init-time file-collision scan (spec 013 T010).

Two tiny offline fixture templates that write a shared path must hard-stop with
CollisionError BEFORE any file appears in the real dest; a disjoint pair passes
silently. The scan must pass skip_tasks=True to every run_copy call (SAFETY:
no task execution during the read-only overlap check).
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import CollisionError
from tests.conftest import TemplateRepo, build_template_repo

_YML = dedent(
    """\
    project_name:
      type: str
    today:
      type: str
      default: ""
    _subdirectory: template
    """
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(name: str, repo: TemplateRepo) -> TemplateRecord:
    return TemplateRecord(
        full_id=f"demo/{name}",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


def _make_pair(tmp_path: Path, *, colliding: bool) -> tuple[TemplateRecord, TemplateRecord]:
    shared_or_b = "shared.txt.jinja" if colliding else "b_only.txt.jinja"
    tpl_a = build_template_repo(
        tmp_path / "col-a",
        files={"copier.yml": _YML, "template/shared.txt.jinja": "a={{ project_name }}\n"},
    )
    tpl_b = build_template_repo(
        tmp_path / "col-b",
        files={"copier.yml": _YML, f"template/{shared_or_b}": "b={{ project_name }}\n"},
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)
    return _record("col-a", tpl_a), _record("col-b", tpl_b)


def test_collision_raises_before_any_write(tmp_path: Path) -> None:
    rec_a, rec_b = _make_pair(tmp_path, colliding=True)
    dest = tmp_path / "out"

    with pytest.raises(CollisionError) as exc_info:
        runner.init_many(
            [(rec_a, {"project_name": "p"}), (rec_b, {"project_name": "p"})],
            str(dest),
            today="2026-07-15",
        )

    err = exc_info.value
    assert err.path == "shared.txt"
    assert set(err.modules) == {"demo/col-a", "demo/col-b"}
    # Dest untouched: no file was written before the hard stop.
    assert not dest.exists() or not any(dest.iterdir())


def test_disjoint_pair_passes_silently(tmp_path: Path) -> None:
    rec_a, rec_b = _make_pair(tmp_path, colliding=False)
    dest = tmp_path / "out"

    results = runner.init_many(
        [(rec_a, {"project_name": "p"}), (rec_b, {"project_name": "p"})],
        str(dest),
        today="2026-07-15",
    )
    assert len(results) == 2
    assert (dest / "shared.txt").is_file()  # col-a's file
    assert (dest / "b_only.txt").is_file()


def test_scan_passes_skip_tasks_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SAFETY: every run_copy in the collision scan must set skip_tasks=True."""
    rec_a, rec_b = _make_pair(tmp_path, colliding=False)
    calls: list[dict] = []

    def _spy_run_copy(*args, **kwargs):
        calls.append(kwargs)
        raise SystemExit("stop after recording")  # do not actually render

    monkeypatch.setattr(runner, "run_copy", _spy_run_copy)
    plan = [(rec_a, ".copier-answers.col-a.yml"), (rec_b, ".copier-answers.col-b.yml")]
    with pytest.raises(SystemExit):
        runner._scan_init_collisions(plan, str(tmp_path / "out"), {}, {})

    assert calls, "run_copy was never invoked by the scan"
    assert all(c.get("skip_tasks") is True for c in calls)


def test_answers_files_excluded_from_overlap(tmp_path: Path) -> None:
    """Both layers write .copier-answers.*.yml-shaped files via the shipped
    answers-file template; those must never count as collisions (the loop in
    test_disjoint_pair_passes_silently would otherwise be impossible)."""
    rec_a, rec_b = _make_pair(tmp_path, colliding=False)
    dest = tmp_path / "out"
    runner.init_many(
        [(rec_a, {"project_name": "p"}), (rec_b, {"project_name": "p"})],
        str(dest),
        today="2026-07-15",
    )
    answers = sorted(p.name for p in dest.glob(".copier-answers*.yml"))
    assert len(answers) == 2
