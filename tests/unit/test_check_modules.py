"""Unit tests for scripts/check_modules.py (spec 008b / T004).

All tests are offline — they build local temp dirs that look like module directories.
No network access, no real git clones needed for the per-module checks.
The published-label immutability check is covered by monkeypatching git tag output.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Import the checker as a module (not subprocess) so we test the real logic.
# The script uses _REPO_ROOT derived from __file__; we override templates_dir
# and cog/catalog paths via direct call to check_modules().
# ---------------------------------------------------------------------------
import importlib.util
import os
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest


def _load_check_modules():
    spec = importlib.util.spec_from_file_location(
        "check_modules",
        Path(__file__).parent.parent.parent / "scripts" / "check_modules.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_cm = _load_check_modules()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATH = os.environ.get("PATH", "/usr/bin:/bin")
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "clerk-test",
    "GIT_AUTHOR_EMAIL": "test@clerk.invalid",
    "GIT_COMMITTER_NAME": "clerk-test",
    "GIT_COMMITTER_EMAIL": "test@clerk.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "PATH": _PATH,
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=_GIT_ENV)


ANSWERS_FILE_TEMPLATE_NAME = "{{ _copier_conf.answers_file }}.jinja"
ANSWERS_FILE_BODY = "# Managed by copier — do not edit.\n{{ _copier_answers|to_nice_yaml }}\n"

_MINIMAL_COPIER_YML = dedent(
    """\
    module_name:
      type: str
      default: mymod
    """
)

_CHOICES_COPIER_YML = dedent(
    """\
    module_name:
      type: str
      default: mymod
    license:
      type: str
      choices: ["MIT", "Apache-2.0"]
      default: MIT
    """
)


def _make_module(
    root: Path,
    name: str,
    *,
    copier_yml: str = _MINIMAL_COPIER_YML,
    add_answers_file: bool = True,
    add_readme: bool = True,
    add_changelog: bool = True,
) -> Path:
    """Build a minimal module directory under root/name."""
    mod = root / name
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "copier.yml").write_text(copier_yml)
    if add_answers_file:
        (mod / ANSWERS_FILE_TEMPLATE_NAME).write_text(ANSWERS_FILE_BODY)
    if add_readme:
        (mod / "README.md").write_text(f"# {name}\n")
    if add_changelog:
        (mod / "CHANGELOG.md").write_text("")
    return mod


def _make_cog_toml(repo_root: Path, packages: list[str]) -> None:
    """Write a minimal cog.toml with the given package names."""
    lines = [
        "generate_mono_repository_global_tag = false",
        'tag_prefix = "v"',
        "",
        "[monorepo.packages]",
    ]
    for pkg in packages:
        lines.append(f"[monorepo.packages.{pkg}]")
        lines.append(f'path = "templates/{pkg}"')
        lines.append("")
    (repo_root / "cog.toml").write_text("\n".join(lines))


def _make_catalog_sources(repo_root: Path, names: list[str]) -> None:
    """Write catalog-sources.toml with the given module names."""
    lines = []
    for name in names:
        lines.append("[[sources]]")
        lines.append(f'url = "https://github.com/copier-clerk/{name}.git"')
        lines.append("")
    (repo_root / "catalog-sources.toml").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Fixture: a fake monorepo root with templates/, cog.toml, etc.
# ---------------------------------------------------------------------------


@pytest.fixture
def mono(tmp_path: Path) -> Path:
    """Return a temp dir acting as the monorepo root.

    Patches _cm._REPO_ROOT so the checker reads cog.toml and catalog-sources.toml
    from this directory, and initialises a git repo for tag checks.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "--allow-empty", "-qm", "init")
    templates = tmp_path / "templates"
    templates.mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# (a) Valid module → exit 0
# ---------------------------------------------------------------------------


def test_valid_module_exits_zero(mono: Path) -> None:
    _make_module(mono / "templates", "clerk-mod-base")
    _make_cog_toml(mono, ["clerk-mod-base"])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 0


# ---------------------------------------------------------------------------
# (b) Missing answers-file .jinja → exit 1, names the module
# ---------------------------------------------------------------------------


def test_missing_answers_file_fails(mono: Path, capsys) -> None:
    _make_module(mono / "templates", "clerk-mod-bad", add_answers_file=False)
    _make_cog_toml(mono, ["clerk-mod-bad"])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 1
    captured = capsys.readouterr()
    assert "clerk-mod-bad" in captured.err
    assert "answers-file" in captured.err


# ---------------------------------------------------------------------------
# (c) Missing README → exit 1
# ---------------------------------------------------------------------------


def test_missing_readme_fails(mono: Path, capsys) -> None:
    _make_module(mono / "templates", "clerk-mod-noreadme", add_readme=False)
    _make_cog_toml(mono, ["clerk-mod-noreadme"])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 1
    captured = capsys.readouterr()
    assert "clerk-mod-noreadme" in captured.err
    assert "README" in captured.err


# ---------------------------------------------------------------------------
# (d) Module in templates/ but absent from cog.toml → exit 1 (parity)
# ---------------------------------------------------------------------------


def test_module_not_in_cog_fails(mono: Path, capsys) -> None:
    _make_module(mono / "templates", "clerk-mod-orphan")
    # cog.toml lists nothing
    _make_cog_toml(mono, [])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 1
    captured = capsys.readouterr()
    assert "clerk-mod-orphan" in captured.err
    assert "cog.toml" in captured.err


# ---------------------------------------------------------------------------
# (e) Module in cog.toml but not in templates/ → exit 1 (ghost)
# ---------------------------------------------------------------------------


def test_ghost_in_cog_fails(mono: Path, capsys) -> None:
    _make_module(mono / "templates", "clerk-mod-real")
    # cog.toml lists an extra ghost module
    _make_cog_toml(mono, ["clerk-mod-real", "clerk-mod-ghost"])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 1
    captured = capsys.readouterr()
    assert "clerk-mod-ghost" in captured.err


# ---------------------------------------------------------------------------
# Empty templates/ → exit 0 (graceful no-op)
# ---------------------------------------------------------------------------


def test_empty_templates_exits_zero(mono: Path) -> None:
    _make_cog_toml(mono, [])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 0


# ---------------------------------------------------------------------------
# Three-way parity with catalog-sources.toml
# ---------------------------------------------------------------------------


def test_three_way_parity_all_present(mono: Path) -> None:
    _make_module(mono / "templates", "clerk-mod-x")
    _make_cog_toml(mono, ["clerk-mod-x"])
    _make_catalog_sources(mono, ["clerk-mod-x"])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 0


def test_three_way_parity_missing_catalog(mono: Path, capsys) -> None:
    _make_module(mono / "templates", "clerk-mod-x")
    _make_cog_toml(mono, ["clerk-mod-x"])
    # catalog-sources.toml exists but doesn't list the module
    _make_catalog_sources(mono, [])

    with patch.object(_cm, "_REPO_ROOT", mono):
        result = _cm.check_modules(mono / "templates")
    assert result == 1
    captured = capsys.readouterr()
    assert "clerk-mod-x" in captured.err
    assert "catalog-sources.toml" in captured.err


# ---------------------------------------------------------------------------
# Published-label immutability (C-06) — monkeypatch git tags
# ---------------------------------------------------------------------------


def test_label_immutability_unchanged_passes(mono: Path) -> None:
    _make_module(mono / "templates", "clerk-mod-y", copier_yml=_CHOICES_COPIER_YML)
    _make_cog_toml(mono, ["clerk-mod-y"])

    # Simulate a published tag existing; tagged copier.yml has same choices
    with (
        patch.object(_cm, "_REPO_ROOT", mono),
        patch.object(_cm, "_git_tags_for_module", return_value=["clerk-mod-y-v1.0.0"]),
        patch.object(
            _cm,
            "_copier_yml_at_ref",
            return_value={
                "license": {"choices": ["MIT", "Apache-2.0"], "type": "str", "default": "MIT"}
            },
        ),
    ):
        result = _cm.check_modules(mono / "templates")
    assert result == 0


def test_label_immutability_changed_fails(mono: Path, capsys) -> None:
    _make_module(mono / "templates", "clerk-mod-z", copier_yml=_CHOICES_COPIER_YML)
    _make_cog_toml(mono, ["clerk-mod-z"])

    # Tagged version had different choices
    with (
        patch.object(_cm, "_REPO_ROOT", mono),
        patch.object(_cm, "_git_tags_for_module", return_value=["clerk-mod-z-v1.0.0"]),
        patch.object(
            _cm,
            "_copier_yml_at_ref",
            return_value={
                "license": {"choices": ["MIT", "GPL-3.0"], "type": "str", "default": "MIT"}
            },
        ),
    ):
        result = _cm.check_modules(mono / "templates")
    assert result == 1
    captured = capsys.readouterr()
    assert "clerk-mod-z" in captured.err
    assert "label" in captured.err.lower() or "mutation" in captured.err
