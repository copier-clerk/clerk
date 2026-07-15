"""Round-trip test for the _meta/module-template/ scaffolder (spec 008b / T008).

Renders the meta-template into a temp directory, then runs check_modules against
the output. Asserts exit 0 — "contract-complete out of the box" (SC-003 / FR-005).
Also asserts cog.toml and catalog-sources.toml contain the registration entries.

All offline: no network access, no git clones.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Load check_modules as a module for direct invocation.
# ---------------------------------------------------------------------------


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

_META_TEMPLATE = Path(__file__).parent.parent.parent / "_meta" / "module-template"
_PATH = os.environ.get("PATH", "/usr/bin:/bin")
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "bailiff-test",
    "GIT_AUTHOR_EMAIL": "test@bailiff.invalid",
    "GIT_COMMITTER_NAME": "bailiff-test",
    "GIT_COMMITTER_EMAIL": "test@bailiff.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "PATH": _PATH,
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=_GIT_ENV)


@pytest.fixture
def scaffolded(tmp_path: Path) -> Path:
    """Render the meta-template into tmp_path with module_name=bailiff-mod-test-fixture.

    Copies cog.toml and scripts/ into the destination so the tasks can register
    the module without touching the real monorepo.  Returns the destination root.
    """
    repo_root = Path(__file__).parent.parent.parent
    # Seed a minimal cog.toml in the destination
    (tmp_path / "cog.toml").write_text(
        "generate_mono_repository_global_tag = false\n"
        'tag_prefix = "v"\n'
        "pre_bump_hooks = []\n\n"
        "[monorepo.packages]\n"
    )
    # Copy scripts/ so the _tasks can call _meta_register.py
    import shutil

    shutil.copytree(repo_root / "scripts", tmp_path / "scripts")

    # Init a git repo so check_modules can run git tag -l
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "--allow-empty", "-qm", "init")

    subprocess.run(
        [
            "uv",
            "run",
            "copier",
            "copy",
            str(_META_TEMPLATE),
            str(tmp_path),
            "--data",
            "module_name=bailiff-mod-test-fixture",
            "--overwrite",
            "--defaults",
            "--trust",
        ],
        check=True,
        capture_output=True,
        cwd=repo_root,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Round-trip: scaffold → check_modules → exit 0
# ---------------------------------------------------------------------------


def test_scaffolded_module_passes_check_modules(scaffolded: Path) -> None:
    """A freshly scaffolded module must pass check_modules immediately (SC-003)."""
    with patch.object(_cm, "_REPO_ROOT", scaffolded):
        result = _cm.check_modules(scaffolded / "templates")
    assert result == 0, "check_modules must exit 0 for a freshly scaffolded module"


# ---------------------------------------------------------------------------
# Check produced files
# ---------------------------------------------------------------------------


def test_scaffolded_module_has_required_files(scaffolded: Path) -> None:
    mod = scaffolded / "templates" / "bailiff-mod-test-fixture"
    assert (mod / "copier.yml").exists(), "copier.yml must be created by scaffold"
    assert (mod / "README.md").exists(), "README.md must be created by scaffold"
    assert (mod / "CHANGELOG.md").exists(), "CHANGELOG.md must be created by scaffold"
    # Answers-file template — filename contains literal Jinja braces
    answers_file = mod / "{{ _copier_conf.answers_file }}.jinja"
    assert answers_file.exists(), (
        "{{ _copier_conf.answers_file }}.jinja must be created by scaffold (FR-016)"
    )


def test_scaffolded_module_copier_yml_has_answers_file_key(scaffolded: Path) -> None:
    import yaml

    copier_yml = (scaffolded / "templates" / "bailiff-mod-test-fixture" / "copier.yml").read_text()
    data = yaml.safe_load(copier_yml) or {}
    assert "_answers_file" in data, "copier.yml must declare _answers_file"
    assert "{{ _copier_conf.answers_file }}" in data["_answers_file"]


# ---------------------------------------------------------------------------
# Check registration entries
# ---------------------------------------------------------------------------


def test_cog_toml_contains_module_entry(scaffolded: Path) -> None:
    cog_text = (scaffolded / "cog.toml").read_text()
    assert "[monorepo.packages.bailiff-mod-test-fixture]" in cog_text
    assert 'path = "templates/bailiff-mod-test-fixture"' in cog_text


def test_catalog_sources_contains_module_url(scaffolded: Path) -> None:
    catalog = scaffolded / "catalog-sources.toml"
    assert catalog.exists(), "catalog-sources.toml must be created by scaffold"
    text = catalog.read_text()
    assert "https://github.com/bailiff-io/bailiff-mod-test-fixture.git" in text
