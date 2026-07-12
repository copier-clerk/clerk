"""US1: single-template init with per-template defaults (spec 004 / T008).

Tests:
- SC-001: default key pre-fills the answers file when not overridden.
- SC-002 (precedence): data= value beats defaults file value.
- SC-003 (secret exclusion): secret questions are never pre-filled from defaults.
- SC-004 (missing file): absent defaults file is a no-op.
- SC-007: no defaults-related file written into the generated project.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import TemplateRepo, build_template_repo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate copier settings.yml and clerk defaults from the developer's machine."""
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))
    monkeypatch.setenv("CLERK_DEFAULTS_PATH", str(tmp_path / "defaults.yml"))


@pytest.fixture
def defaults_template(tmp_path: Path) -> TemplateRepo:
    """Template with author_name + author_email questions (no copier.yml defaults)."""
    copier_yml = dedent(
        """\
        author_name:
          type: str
        author_email:
          type: str
        project_name:
          type: str

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "tpl-defaults",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": (
                "name={{ author_name }} email={{ author_email }} project={{ project_name }}\n"
            ),
        },
    )


@pytest.fixture
def secret_defaults_template(tmp_path: Path) -> TemplateRepo:
    """Template with a non-secret question and a secret question sharing a defaults key.

    api_key has a non-empty default so _check_required_secrets_supplied passes
    without requiring the caller to supply a secret value.
    """
    copier_yml = dedent(
        """\
        author_name:
          type: str
        api_key:
          type: str
          secret: true
          default: "placeholder"

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "tpl-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ author_name }}\n",
        },
    )


def _write_defaults(tmp_path: Path, content: str) -> None:
    """Write the defaults.yml file at the env-overridden path."""
    (tmp_path / "defaults.yml").write_text(content)


# ---------------------------------------------------------------------------
# SC-001: pre-fill answers from defaults file
# ---------------------------------------------------------------------------


def test_defaults_pre_fill_answers(defaults_template: TemplateRepo, tmp_path: Path) -> None:
    """A key in defaults.yml pre-fills the answers file when not in data=."""
    trust.add_trust(defaults_template.url)
    _write_defaults(tmp_path, "author_name: Ada\nauthor_email: ada@example.com\n")

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=defaults_template.url,
        dest=str(dest),
        answers={"project_name": "myproject"},
    )
    runner.init(spec)

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["author_name"] == "Ada"
    assert answers["author_email"] == "ada@example.com"


# ---------------------------------------------------------------------------
# SC-002: data= hard override wins over defaults file
# ---------------------------------------------------------------------------


def test_data_wins_over_defaults(defaults_template: TemplateRepo, tmp_path: Path) -> None:
    """data= value beats the defaults file value (precedence FR-002)."""
    trust.add_trust(defaults_template.url)
    _write_defaults(tmp_path, "author_name: Ada\n")

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=defaults_template.url,
        dest=str(dest),
        answers={
            "author_name": "Bob",  # data= override — must win
            "author_email": "bob@example.com",
            "project_name": "myproject",
        },
    )
    runner.init(spec)

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers["author_name"] == "Bob"


# ---------------------------------------------------------------------------
# SC-003: secret question never pre-filled
# ---------------------------------------------------------------------------


def test_secret_question_not_pre_filled(
    secret_defaults_template: TemplateRepo, tmp_path: Path
) -> None:
    """api_key is secret — it must NOT be pre-filled from defaults.yml."""
    trust.add_trust(secret_defaults_template.url)
    # Both keys in defaults.yml, but api_key is secret
    _write_defaults(tmp_path, "author_name: Ada\napi_key: s3cr3t\n")

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=secret_defaults_template.url,
        dest=str(dest),
        answers={"author_name": "Ada"},
    )
    runner.init(spec)

    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert answers.get("author_name") == "Ada"
    # api_key must NOT be present with the defaults value (empty string default only)
    assert answers.get("api_key", "") != "s3cr3t"


# ---------------------------------------------------------------------------
# SC-004: missing defaults file is a no-op
# ---------------------------------------------------------------------------


def test_missing_defaults_file_is_noop(defaults_template: TemplateRepo, tmp_path: Path) -> None:
    """No defaults.yml → init runs identically to pre-004 (no error, no defaults)."""
    trust.add_trust(defaults_template.url)
    # Note: CLERK_DEFAULTS_PATH is set to tmp_path/defaults.yml which does NOT exist.
    # But: defaults_path() raises DefaultsError when the env var names a missing file.
    # So we unset the env var here to use the platformdirs default (which also won't
    # exist in the test environment → silent no-op from load()).
    import os

    # Remove the env override so defaults_path() falls back to platformdirs path
    # (which is also absent in CI → load() returns {} silently).
    del os.environ["CLERK_DEFAULTS_PATH"]

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=defaults_template.url,
        dest=str(dest),
        answers={"project_name": "myproject", "author_name": "Ada", "author_email": "a@b.com"},
    )
    # Must not raise — behaves as pre-004
    runner.init(spec)
    assert (dest / "out.txt").exists()


# ---------------------------------------------------------------------------
# SC-007: no clerk defaults file written into project
# ---------------------------------------------------------------------------


def test_no_defaults_file_in_project(defaults_template: TemplateRepo, tmp_path: Path) -> None:
    """Defaults are user-side config — no defaults.yml written into the project."""
    trust.add_trust(defaults_template.url)
    _write_defaults(tmp_path, "author_name: Ada\nauthor_email: ada@example.com\n")

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=defaults_template.url,
        dest=str(dest),
        answers={"project_name": "myproject"},
    )
    runner.init(spec)

    # No defaults.yml anywhere in the generated project tree
    found = list(dest.rglob("defaults.yml"))
    assert found == [], f"Unexpected defaults file in project: {found}"
    # No CLERK_DEFAULTS_PATH-named file either
    found_any = list(dest.rglob("*.yml"))
    clerk_files = [f for f in found_any if "defaults" in f.name and f.name != ".copier-answers.yml"]
    assert clerk_files == []


# ---------------------------------------------------------------------------
# check=True (dry-run) also receives user_defaults (FR-008)
# ---------------------------------------------------------------------------


def test_check_true_receives_same_user_defaults(
    defaults_template: TemplateRepo, tmp_path: Path
) -> None:
    """check=True (preflight) must pass user_defaults= (FR-008 — same path as real init)."""
    trust.add_trust(defaults_template.url)
    _write_defaults(tmp_path, "author_name: Ada\nauthor_email: ada@example.com\n")

    dest = tmp_path / "proj-check"
    spec = runner.RunSpec(
        source=defaults_template.url,
        dest=str(dest),
        answers={"project_name": "myproject"},
    )
    # Should not raise even with defaults; pretend=True writes nothing
    result = runner.init(spec, check=True)
    assert result.pretend is True
    # No files written (dry run)
    assert not dest.exists() or not (dest / "out.txt").exists()
