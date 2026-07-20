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


_PRODUCER_YML = dedent(
    """\
    project_name:
      type: str
    today:
      type: str
      default: ""
    _subdirectory: template
    """
)

_CONSUMER_YML = dedent(
    """\
    _external_data:
      base: .copier-answers.producer.yml
    project_name:
      type: str
      default: "{{ _external_data.base.project_name | default('', true) }}"
    today:
      type: str
      default: ""
    depends_on:
      type: yaml
      default:
        - producer
      when: false
    _subdirectory: template
    """
)


def test_external_data_consumers_are_scanned_for_collisions(tmp_path: Path) -> None:
    """Regression: a collision BETWEEN two _external_data consumers must be caught.

    Consumers render alone in the scan (no producer answers file present), so
    copier resolves the alias to {}. Before the realpath fix the solo render
    raised ForbiddenPathError (macOS $TMPDIR /var→/private/var symlink), which the
    scan swallowed as "skip this layer" — silently disabling overlap detection for
    ~20 of 27 real modules. The scan must now render both consumers and hard-stop.
    """
    producer = build_template_repo(
        tmp_path / "producer",
        files={
            "copier.yml": _PRODUCER_YML,
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# {{ _copier_conf.answers_file }}\n{{ _copier_answers|to_nice_yaml }}\n"
            ),
        },
    )
    # Two consumers that BOTH read base via _external_data and BOTH write clash.txt.
    con_a = build_template_repo(
        tmp_path / "con-a",
        files={
            "copier.yml": _CONSUMER_YML,
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# {{ _copier_conf.answers_file }}\n{{ _copier_answers|to_nice_yaml }}\n"
            ),
            "template/clash.txt.jinja": "a={{ _external_data.base.project_name }}\n",
        },
    )
    con_b = build_template_repo(
        tmp_path / "con-b",
        files={
            "copier.yml": _CONSUMER_YML,
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# {{ _copier_conf.answers_file }}\n{{ _copier_answers|to_nice_yaml }}\n"
            ),
            "template/clash.txt.jinja": "b={{ _external_data.base.project_name }}\n",
        },
    )
    for repo in (producer, con_a, con_b):
        trust.add_trust(repo.url)

    dest = tmp_path / "out"
    with pytest.raises(CollisionError) as exc_info:
        runner.init_many(
            [
                (_record("producer", producer), {"project_name": "p"}),
                (_record("con-a", con_a), {}),
                (_record("con-b", con_b), {}),
            ],
            str(dest),
            today="2026-07-15",
        )
    assert exc_info.value.path == "clash.txt"
    assert set(exc_info.value.modules) == {"demo/con-a", "demo/con-b"}
    assert not dest.exists() or not any(dest.iterdir())


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


def test_canonical_dest_resolves_symlinked_prefix(tmp_path: Path) -> None:
    """A dest under a symlinked prefix must resolve so copier's _external_data
    path check agrees (macOS /tmp → /private/tmp otherwise → ForbiddenPathError).
    """
    import os

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    got = runner._canonical_dest(str(link / "proj"))
    # The symlink component is resolved; the not-yet-created leaf stays literal.
    assert got == os.path.realpath(str(link / "proj"))
    assert "/link/" not in got and got.endswith("/proj")


def test_reproduce_under_symlinked_dest_no_forbidden_path(tmp_path: Path) -> None:
    """reproduce() of an _external_data consumer under a symlinked prefix must not
    raise copier's ForbiddenPathError — every dest entry point canonicalizes (FR-013
    class, extended to reproduce/update)."""
    producer = build_template_repo(
        tmp_path / "producer",
        files={
            "copier.yml": _PRODUCER_YML,
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# {{ _copier_conf.answers_file }}\n{{ _copier_answers|to_nice_yaml }}\n"
            ),
        },
    )
    consumer = build_template_repo(
        tmp_path / "consumer",
        files={
            "copier.yml": _CONSUMER_YML,
            "template/{{ _copier_conf.answers_file }}.jinja": (
                "# {{ _copier_conf.answers_file }}\n{{ _copier_answers|to_nice_yaml }}\n"
            ),
            "template/who.txt.jinja": "name={{ _external_data.base.project_name }}\n",
        },
    )
    for repo in (producer, consumer):
        trust.add_trust(repo.url)

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    dest = link / "proj"  # dest reached THROUGH the symlink

    runner.init_many(
        [
            (_record("producer", producer), {"project_name": "p"}),
            (_record("consumer", consumer), {}),
        ],
        str(dest),
        today="2026-07-20",
    )
    # Reproduce through the symlinked path: must succeed (canonicalized internally),
    # not raise copier's ForbiddenPathError on the consumer's _external_data read.
    results = runner.reproduce_many(str(dest))
    assert len(results) == 2
