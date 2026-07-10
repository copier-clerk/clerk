"""US1: generate a reproducible project (FR-007, FR-011, FR-012, FR-012a)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import TemplateRepo


def _trust(repo: TemplateRepo) -> None:
    trust.add_trust(repo.url)  # exact-match trust for the local fixture source


def _spec(repo: TemplateRepo, dest: Path, **answers: str) -> runner.RunSpec:
    base = {"project_name": "demo"}
    base.update(answers)
    return runner.RunSpec(source=repo.url, dest=str(dest), answers=base)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_init_renders_files_and_records_answers(
    base_template: TemplateRepo, tmp_path: Path
) -> None:
    _trust(base_template)
    dest = tmp_path / "proj"
    runner.init(_spec(base_template, dest, org="acme"), today="2026-07-09")

    assert (
        dest / "out.txt"
    ).read_text().strip() == "name=demo org=acme license=Apache-2.0 date=2026-07-09"
    assert (dest / "README.md").exists()
    # the git-init task ran (FR-018)
    assert (dest / ".git").is_dir()

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["project_name"] == "demo"
    assert answers["_commit"] == base_template.tag  # exact version recorded
    assert answers["_src_path"] == base_template.url  # fetchable source (FR-012a)


def test_today_is_frozen_into_answers(base_template: TemplateRepo, tmp_path: Path) -> None:
    _trust(base_template)
    dest = tmp_path / "proj"
    runner.init(_spec(base_template, dest), today="2020-01-01")
    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    # the injected date is persisted verbatim (FR-007) — not the wall clock
    assert answers["today"] == "2020-01-01"
    assert (dest / "out.txt").read_text().strip().endswith("date=2020-01-01")


def test_missing_required_answer_is_refused(base_template: TemplateRepo, tmp_path: Path) -> None:
    _trust(base_template)
    dest = tmp_path / "proj"
    # omit the required project_name → clerk surfaces a legible error, no files
    spec = runner.RunSpec(source=base_template.url, dest=str(dest), answers={})
    from clerk.errors import InvalidRunSpecError

    with pytest.raises(InvalidRunSpecError):
        runner.init(spec, today="2026-07-09")
    assert not (dest / "out.txt").exists()
