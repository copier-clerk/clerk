"""spec 014 SC-006/SC-008/FR-014/R10: _bailiff_schema migration gate.

Tests:
- Post-render: bailiff appends _bailiff_schema: "014" to each answers file
- reproduce_many: pre-014 answers file (no _bailiff_schema) → loud error + re-init guidance
- reproduce_many: answers file with wrong schema version → loud error
- reproduce_many: correct schema → succeeds
- _bailiff_schema must NOT be a regular copier answer (not user-overridable)
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from bailiff.errors import BailiffError
from tests.conftest import build_template_repo

_SCHEMA_VERSION = "014"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _record(full_id: str, repo, questions: list[str] | None = None) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=questions or ["project_name"],
    )


def _simple_template(root: Path, name: str) -> object:
    """Build a simple one-question template repo."""
    return build_template_repo(
        root / name,
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )


# ---------------------------------------------------------------------------
# Marker written post-render
# ---------------------------------------------------------------------------


def test_schema_marker_written_after_init(tmp_path: Path) -> None:
    """After init_many, each .copier-answers.<name>.yml carries _bailiff_schema: '014'."""
    tpl = _simple_template(tmp_path, "mod-alpha")
    trust.add_trust(tpl.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("testcat/mod-alpha", tpl), {"project_name": "demo"})],
        str(dest),
        today="2026-07-16",
    )

    af_path = dest / ".copier-answers.mod-alpha.yml"
    assert af_path.exists()
    raw = yaml.safe_load(af_path.read_text()) or {}
    assert "_bailiff_schema" in raw, (
        f"_bailiff_schema missing from answers file; got keys: {list(raw)}"
    )
    assert raw["_bailiff_schema"] == _SCHEMA_VERSION, (
        f"Expected _bailiff_schema={_SCHEMA_VERSION!r}, got {raw['_bailiff_schema']!r}"
    )


def test_schema_marker_written_for_each_layer(tmp_path: Path) -> None:
    """_bailiff_schema is written to EACH layer's answers file in a multi-layer init."""
    tpl_a = _simple_template(tmp_path, "mod-a")
    tpl_b = build_template_repo(
        tmp_path / "mod-b",
        files={
            "copier.yml": dedent(
                """\
                project_name:
                  type: str
                depends_on:
                  type: yaml
                  default: ["mod-a"]
                  when: false
                _subdirectory: template
                """
            ),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    trust.add_trust(tpl_a.url)
    trust.add_trust(tpl_b.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [
            (_record("testcat/mod-a", tpl_a), {"project_name": "demo"}),
            (_record("testcat/mod-b", tpl_b), {"project_name": "demo"}),
        ],
        str(dest),
        today="2026-07-16",
    )

    for name in ("mod-a", "mod-b"):
        af = yaml.safe_load((dest / f".copier-answers.{name}.yml").read_text()) or {}
        assert af.get("_bailiff_schema") == _SCHEMA_VERSION, (
            f"{name}: _bailiff_schema missing or wrong: {af.get('_bailiff_schema')!r}"
        )


# ---------------------------------------------------------------------------
# reproduce_many refuses pre-014 answers files (SC-006/SC-008)
# ---------------------------------------------------------------------------


def test_reproduce_refuses_pre_014_answers_file(tmp_path: Path) -> None:
    """reproduce_many refuses when a recorded answers file lacks _bailiff_schema (SC-006).

    A pre-014 tree cannot have the marker. reproduce must produce a LOUD error with
    re-init guidance instead of silently mis-rendering (FR-014/R10).
    """
    tpl = _simple_template(tmp_path, "mod-alpha")
    trust.add_trust(tpl.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("testcat/mod-alpha", tpl), {"project_name": "demo"})],
        str(dest),
        today="2026-07-16",
    )

    # Simulate a pre-014 tree by removing _bailiff_schema from the answers file
    af_path = dest / ".copier-answers.mod-alpha.yml"
    raw = yaml.safe_load(af_path.read_text()) or {}
    raw.pop("_bailiff_schema", None)
    af_path.write_text(yaml.dump(raw))

    with pytest.raises(BailiffError) as exc_info:
        runner.reproduce_many(str(dest))

    msg = str(exc_info.value)
    # Must mention re-init (guidance)
    assert "init" in msg.lower() or "re-init" in msg.lower() or "reinit" in msg.lower(), (
        f"Error must include re-init guidance, got: {msg!r}"
    )
    # Must mention the schema / version concept
    assert "schema" in msg.lower() or "014" in msg, f"Error must mention schema/014, got: {msg!r}"


def test_reproduce_refuses_wrong_schema_version(tmp_path: Path) -> None:
    """reproduce_many refuses when _bailiff_schema carries an older/wrong version."""
    tpl = _simple_template(tmp_path, "mod-alpha")
    trust.add_trust(tpl.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("testcat/mod-alpha", tpl), {"project_name": "demo"})],
        str(dest),
        today="2026-07-16",
    )

    # Set a wrong schema version
    af_path = dest / ".copier-answers.mod-alpha.yml"
    raw = yaml.safe_load(af_path.read_text()) or {}
    raw["_bailiff_schema"] = "013"
    af_path.write_text(yaml.dump(raw))

    with pytest.raises(BailiffError) as exc_info:
        runner.reproduce_many(str(dest))

    msg = str(exc_info.value)
    assert "schema" in msg.lower() or "013" in msg or "014" in msg, (
        f"Error must mention schema version, got: {msg!r}"
    )


def test_reproduce_succeeds_with_correct_schema(tmp_path: Path) -> None:
    """reproduce_many succeeds when _bailiff_schema = '014' is present."""
    tpl = _simple_template(tmp_path, "mod-alpha")
    trust.add_trust(tpl.url)

    dest = tmp_path / "proj"
    runner.init_many(
        [(_record("testcat/mod-alpha", tpl), {"project_name": "demo"})],
        str(dest),
        today="2026-07-16",
    )

    # Confirm marker is present (init should have written it)
    af_path = dest / ".copier-answers.mod-alpha.yml"
    raw = yaml.safe_load(af_path.read_text()) or {}
    assert raw.get("_bailiff_schema") == _SCHEMA_VERSION

    # reproduce must succeed
    runner.reproduce_many(str(dest))
    # after reproduce, marker must still be present
    raw2 = yaml.safe_load(af_path.read_text()) or {}
    assert raw2.get("_bailiff_schema") == _SCHEMA_VERSION, (
        "reproduce removed/changed _bailiff_schema marker"
    )


# ---------------------------------------------------------------------------
# _bailiff_schema is not a user-overridable copier answer
# ---------------------------------------------------------------------------


def test_schema_marker_is_not_a_user_answer(tmp_path: Path) -> None:
    """_bailiff_schema is a bailiff-written metadata key, not a copier question.

    Supplying _bailiff_schema in the run-spec answers dict must NOT override the
    bailiff-written value — the engine writes it independently.
    """
    tpl = _simple_template(tmp_path, "mod-alpha")
    trust.add_trust(tpl.url)

    dest = tmp_path / "proj"
    # Supply a bogus value as if a user tried to override it
    runner.init_many(
        [(_record("testcat/mod-alpha", tpl), {"project_name": "demo", "_bailiff_schema": "999"})],
        str(dest),
        today="2026-07-16",
    )

    af_path = dest / ".copier-answers.mod-alpha.yml"
    raw = yaml.safe_load(af_path.read_text()) or {}
    # Bailiff's write must have set the correct version, not "999"
    assert raw.get("_bailiff_schema") == _SCHEMA_VERSION, (
        f"_bailiff_schema should be '{_SCHEMA_VERSION}' (bailiff-written), "
        f"got {raw.get('_bailiff_schema')!r}"
    )
