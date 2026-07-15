"""Unit tests for the init-time capability conflict warning (spec 013 T009).

The warning is warn-only (never raises) and applies to init_many only —
reproduce/update paths are untouched (FR-012 / SC-008). Tests exercise
``_check_capability_conflicts`` directly plus its wiring inside ``init_many``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from bailiff import discovery, runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import build_template_repo


def _record(name: str, provides: list[str], source: str = "") -> TemplateRecord:
    return TemplateRecord(
        full_id=f"demo/{name}",
        source=source or f"https://example.com/{name}.git",
        ref="v1.0.0",
        versions=["v1.0.0"],
        reproducible=True,
        has_tasks=False,
        questions=[],
        provides=provides,
    )


def test_single_provider_no_warning(tmp_path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        runner._check_capability_conflicts(
            [_record("mod-a", ["python-project"])],
            str(tmp_path),
            frozenset({"python-project"}),
        )


def test_two_providers_non_exclusive_no_warning(tmp_path: Path) -> None:
    """Two providers of a capability nobody declares exclusive: silent."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        runner._check_capability_conflicts(
            [_record("mod-a", ["quality"]), _record("mod-b", ["quality"])],
            str(tmp_path),
            frozenset(),  # no module in the catalog declares quality exclusive
        )


def test_two_providers_exclusive_warns(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="CAPABILITY CONFLICT"):
        runner._check_capability_conflicts(
            [_record("mod-a", ["python-project"]), _record("mod-b", ["python-project"])],
            str(tmp_path),
            frozenset({"python-project"}),
        )


def test_group_infection_third_module_declares_exclusive(tmp_path: Path) -> None:
    """Neither selected module declares exclusive itself; a third (unselected)
    catalog module does — the pre-computed frozenset carries that infection."""
    with pytest.warns(UserWarning, match="python-project"):
        runner._check_capability_conflicts(
            [_record("mod-a", ["python-project"]), _record("mod-b", ["python-project"])],
            str(tmp_path),
            frozenset({"python-project"}),  # infected by the unselected third module
        )


def test_incremental_add_reads_installed_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dest already contains a module providing the capability; adding another
    provider of the same exclusive capability warns (FR-011)."""
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / ".copier-answers.mod-installed.yml").write_text(
        "_src_path: https://example.com/mod-installed.git\n_commit: v1.0.0\n"
    )

    def _fake_discover(source: str, ref: str | None = None) -> discovery.Discovery:
        return discovery.Discovery(
            source=source,
            ref=ref or "v1.0.0",
            versions=["v1.0.0"],
            reproducible=True,
            has_tasks=False,
            jinja_extensions=[],
            questions=[],
            secret_questions=[],
            provides=["python-project"],
            exclusive=True,
        )

    monkeypatch.setattr(runner.discovery, "discover", _fake_discover)
    with pytest.warns(UserWarning, match="mod-installed"):
        runner._check_capability_conflicts(
            [_record("mod-new", ["python-project"])],
            str(dest),
            frozenset({"python-project"}),
        )


def test_no_capability_modules_silent_and_unchanged(tmp_path: Path) -> None:
    """Modules with no capability declarations behave exactly as pre-013 (SC-003)."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        runner._check_capability_conflicts(
            [_record("mod-a", []), _record("mod-b", [])],
            str(tmp_path),
            frozenset({"anything"}),
        )


def test_init_many_emits_warning_and_still_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: init_many warns on an exclusive conflict but renders anyway."""
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))
    single_yml = (
        "project_name:\n  type: str\ntoday:\n  type: str\n  default: ''\n_subdirectory: template\n"
    )
    tpl_a = build_template_repo(
        tmp_path / "cap-a",
        files={"copier.yml": single_yml, "template/a.txt.jinja": "a={{ project_name }}\n"},
    )
    tpl_b = build_template_repo(
        tmp_path / "cap-b",
        files={"copier.yml": single_yml, "template/b.txt.jinja": "b={{ project_name }}\n"},
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)
    rec_a = _record("cap-a", ["thing"], source=tpl_a.url)
    rec_b = _record("cap-b", ["thing"], source=tpl_b.url)
    dest = tmp_path / "out"

    with pytest.warns(UserWarning, match="CAPABILITY CONFLICT"):
        results = runner.init_many(
            [(rec_a, {"project_name": "p"}), (rec_b, {"project_name": "p"})],
            str(dest),
            today="2026-07-15",
            exclusive_capabilities=frozenset({"thing"}),
        )
    assert len(results) == 2
    assert (dest / "a.txt").is_file()
    assert (dest / "b.txt").is_file()
