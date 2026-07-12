"""US2: per-layer defaults in multi-template init (spec 004 / T010).

Tests:
- SC-005 (per-layer): defaults apply independently per layer in init_many.
- SC-002 (threaded answer wins): a threaded data= answer from layer A beats
  the defaults file value for the same key in layer B.
- SC-007: no defaults file written into the project tree.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from clerk import runner, trust
from clerk.catalog import TemplateRecord
from tests.conftest import TemplateRepo, build_template_repo

# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))
    monkeypatch.setenv("CLERK_DEFAULTS_PATH", str(tmp_path / "defaults.yml"))


def _write_defaults(tmp_path: Path, content: str) -> None:
    (tmp_path / "defaults.yml").write_text(content)


def _make_record(full_id: str, repo: TemplateRepo) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["author_name"],
    )


# ---------------------------------------------------------------------------
# Fixtures: two independent templates each asking author_name
# ---------------------------------------------------------------------------


@pytest.fixture
def tpl_layer_a(tmp_path: Path) -> TemplateRepo:
    copier_yml = dedent(
        """\
        author_name:
          type: str

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "tpl-layer-a",
        files={
            "copier.yml": copier_yml,
            "template/a_out.txt.jinja": "a={{ author_name }}\n",
        },
    )


@pytest.fixture
def tpl_layer_b(tmp_path: Path) -> TemplateRepo:
    copier_yml = dedent(
        """\
        author_name:
          type: str

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "tpl-layer-b",
        files={
            "copier.yml": copier_yml,
            "template/b_out.txt.jinja": "b={{ author_name }}\n",
        },
    )


# ---------------------------------------------------------------------------
# SC-005: per-layer defaults — both layers record the default value
# ---------------------------------------------------------------------------


def test_defaults_apply_per_layer(
    tpl_layer_a: TemplateRepo, tpl_layer_b: TemplateRepo, tmp_path: Path
) -> None:
    """defaults.yml author_name pre-fills both layer A and layer B independently."""
    trust.add_trust(tpl_layer_a.url)
    trust.add_trust(tpl_layer_b.url)
    _write_defaults(tmp_path, "author_name: Ada\n")

    dest = tmp_path / "proj"
    selection = [
        (_make_record("cat/tpl-layer-a", tpl_layer_a), {}),
        (_make_record("cat/tpl-layer-b", tpl_layer_b), {}),
    ]
    runner.init_many(selection, str(dest))

    af_a = yaml.safe_load((dest / ".copier-answers.tpl-layer-a.yml").read_text())
    af_b = yaml.safe_load((dest / ".copier-answers.tpl-layer-b.yml").read_text())
    assert af_a["author_name"] == "Ada", "Layer A should receive the default"
    assert af_b["author_name"] == "Ada", "Layer B should receive the default independently"


# ---------------------------------------------------------------------------
# SC-002 (multi): threaded data= answer from earlier layer beats defaults
# ---------------------------------------------------------------------------


def test_threaded_answer_beats_defaults(
    tpl_layer_a: TemplateRepo, tpl_layer_b: TemplateRepo, tmp_path: Path
) -> None:
    """Layer A's explicit data= answer threads forward and wins over defaults for layer B."""
    trust.add_trust(tpl_layer_a.url)
    trust.add_trust(tpl_layer_b.url)
    # defaults.yml says "Ada", but layer A provides "Org" explicitly
    _write_defaults(tmp_path, "author_name: Ada\n")

    dest = tmp_path / "proj"
    selection = [
        (_make_record("cat/tpl-layer-a", tpl_layer_a), {"author_name": "Org"}),
        (_make_record("cat/tpl-layer-b", tpl_layer_b), {}),
    ]
    runner.init_many(selection, str(dest))

    # Layer A recorded "Org" (from explicit data=)
    af_a = yaml.safe_load((dest / ".copier-answers.tpl-layer-a.yml").read_text())
    assert af_a["author_name"] == "Org"

    # Layer B: "Org" was threaded in via accumulated data= (priority > user_defaults=)
    af_b = yaml.safe_load((dest / ".copier-answers.tpl-layer-b.yml").read_text())
    assert af_b["author_name"] == "Org", "Threaded data= must beat defaults for layer B"


# ---------------------------------------------------------------------------
# SC-007: no defaults file written into the project
# ---------------------------------------------------------------------------


def test_no_defaults_file_in_project_multi(
    tpl_layer_a: TemplateRepo, tpl_layer_b: TemplateRepo, tmp_path: Path
) -> None:
    """No defaults.yml written into the generated project (spec-010 invariant)."""
    trust.add_trust(tpl_layer_a.url)
    trust.add_trust(tpl_layer_b.url)
    _write_defaults(tmp_path, "author_name: Ada\n")

    dest = tmp_path / "proj"
    selection = [
        (_make_record("cat/tpl-layer-a", tpl_layer_a), {}),
        (_make_record("cat/tpl-layer-b", tpl_layer_b), {}),
    ]
    runner.init_many(selection, str(dest))

    found = list(dest.rglob("defaults.yml"))
    assert found == [], f"Unexpected defaults file in project: {found}"
