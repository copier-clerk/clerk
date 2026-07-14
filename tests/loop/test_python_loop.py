"""spec 011 T006: clerk-mod-python v1.0.0 loop tests.

Contract: specs/011-deopinionated-module-family/contracts/clerk-mod-python.md

Covers:
  - init [base, python] uv/3.13/src: ruff.toml MANAGED, pyproject present (task-output),
    mise sentinel present, gitignore_stack threaded.
  - standalone init with defaults: renders ruff.toml, pyproject present.
  - reproduce: ruff.toml byte-identical (MANAGED), pyproject present/structure only
    (TASK-OUTPUT seed-once, no regeneration over populated tree).
  - SEED-ONCE: pyproject not clobbered on re-run when already present.
  - pdm variant: pyproject present, sentinel written.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from clerk import runner, trust
from clerk.catalog import TemplateRecord
from tests.conftest import TemplateRepo


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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# init [base, python] — uv / 3.13 / src                                       #
# --------------------------------------------------------------------------- #


def test_base_python_init_uv_src(
    clerk_mod_base: TemplateRepo, clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """[base, python] uv/3.13/src: ruff.toml managed, pyproject present, mise sentinel."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["ghg:macOS", "gh:Python"],
            },
        ),
        (
            _record(
                "demo/clerk-mod-python",
                clerk_mod_python,
                ["project_name", "python_version", "python_pkg_manager", "python_layout"],
            ),
            {
                "python_pkg_manager": "uv",
                "python_version": "3.13",
                "python_layout": "src",
                "ruff_line_length": "88",
                "ruff_quote_style": "double",
                "ruff_rule_profile": "standard",
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")

    # Base rendered.
    assert (dest / "AGENTS.md").is_file(), "base AGENTS.md missing"

    # TASK-OUTPUT: pyproject.toml present (written by native init stub).
    # Lifecycle: assert presence + structure only, never exact content (R5).
    pyproject = dest / "pyproject.toml"
    assert pyproject.is_file(), "pyproject.toml missing after init"
    pyproject_text = pyproject.read_text()
    assert "[project]" in pyproject_text, "pyproject.toml lacks [project] section"
    assert 'name = "myapp"' in pyproject_text, "project_name not in pyproject"
    assert 'requires-python = ">=3.13"' in pyproject_text, "python_version not in pyproject"

    # Init-only-guard sentinel written (mise install ran).
    assert (dest / ".clerk-python-mise-installed").is_file(), "mise sentinel missing"

    # MANAGED: ruff.toml present and contains the configured values.
    ruff_toml = dest / "ruff.toml"
    assert ruff_toml.is_file(), "ruff.toml missing after init"
    ruff_text = ruff_toml.read_text()
    assert "target-version" in ruff_text, "ruff.toml missing target-version"
    assert 'target-version = "py313"' in ruff_text, (
        "target-version not threaded from python_version"
    )
    assert "line-length = 88" in ruff_text, "line-length not set"
    assert 'quote-style = "double"' in ruff_text, "quote-style not set"
    assert '"E"' in ruff_text, "standard lint rules missing"
    # strict rules NOT present for standard profile.
    assert '"ANN"' not in ruff_text, "strict ANN rule present in standard profile"

    # Answers files recorded.
    af_py = yaml.safe_load((dest / ".copier-answers.clerk-mod-python.yml").read_text())
    assert af_py["python_version"] == "3.13"
    assert af_py["python_pkg_manager"] == "uv"
    assert af_py["python_layout"] == "src"
    assert af_py["ruff_line_length"] == "88"
    assert af_py["ruff_quote_style"] == "double"
    assert af_py["ruff_rule_profile"] == "standard"


# --------------------------------------------------------------------------- #
# reproduce: ruff.toml byte-identical, pyproject presence only                 #
# --------------------------------------------------------------------------- #


def test_reproduce_ruff_managed_pyproject_preserved(
    clerk_mod_base: TemplateRepo, clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """reproduce: ruff.toml byte-identical (MANAGED); pyproject present but not regenerated."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license", "layout"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": ["ghg:macOS", "gh:Python"],
            },
        ),
        (
            _record(
                "demo/clerk-mod-python",
                clerk_mod_python,
                ["project_name", "python_version", "python_pkg_manager"],
            ),
            {
                "python_pkg_manager": "uv",
                "python_version": "3.13",
                "python_layout": "src",
                "ruff_line_length": "88",
                "ruff_quote_style": "double",
                "ruff_rule_profile": "standard",
            },
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")

    ruff_before = _digest(dest / "ruff.toml")
    pyproject_before = _digest(dest / "pyproject.toml")

    runner.reproduce_many(str(dest))

    # MANAGED: ruff.toml byte-identical after reproduce.
    assert _digest(dest / "ruff.toml") == ruff_before, "ruff.toml changed on reproduce"

    # TASK-OUTPUT/seed-once: pyproject.toml present; the `test -f` guard + _skip_if_exists
    # make it a no-op on reproduce — committed file used verbatim (R5).
    assert (dest / "pyproject.toml").is_file(), "pyproject.toml missing after reproduce"
    assert _digest(dest / "pyproject.toml") == pyproject_before, (
        "pyproject.toml changed on reproduce (seed-once guard should prevent regeneration)"
    )


# --------------------------------------------------------------------------- #
# SEED-ONCE: pyproject not clobbered on re-run with project edits              #
# --------------------------------------------------------------------------- #


def test_pyproject_seed_once_not_clobbered(
    clerk_mod_base: TemplateRepo, clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """SEED-ONCE: hand-edited pyproject.toml is preserved on reproduce."""
    trust.add_trust(clerk_mod_base.url)
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/clerk-mod-base", clerk_mod_base, ["project_name", "license"]),
            {"project_name": "myapp", "org": "acme", "license": "mit", "layout": "single"},
        ),
        (
            _record("demo/clerk-mod-python", clerk_mod_python, ["project_name", "python_version"]),
            {"python_pkg_manager": "uv", "python_version": "3.13", "python_layout": "src"},
        ),
    ]
    runner.init_many(selection, str(dest), today="2026-07-13")

    # Simulate project ownership: edit pyproject.toml after init.
    project_edit = '[project]\nname = "myapp"\ndependencies = ["fastapi"]  # added by project\n'
    (dest / "pyproject.toml").write_text(project_edit)

    runner.reproduce_many(str(dest))

    # Seed-once: project edit preserved.
    assert (dest / "pyproject.toml").read_text() == project_edit, (
        "pyproject.toml was clobbered on reproduce (seed-once broken)"
    )


# --------------------------------------------------------------------------- #
# standalone: renders with defaults                                            #
# --------------------------------------------------------------------------- #


def test_standalone_renders_with_defaults(clerk_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """Standalone init (no base layer) renders ruff.toml and pyproject with default values."""
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "uv",
            "python_version": "3.13",
            "python_layout": "src",
            "ruff_line_length": "88",
            "ruff_quote_style": "double",
            "ruff_rule_profile": "standard",
        },
    )
    runner.init(spec, today="2026-07-13")

    # ruff.toml present with defaults.
    ruff_text = (dest / "ruff.toml").read_text()
    assert 'target-version = "py313"' in ruff_text
    assert "line-length = 88" in ruff_text
    assert 'quote-style = "double"' in ruff_text

    # pyproject present (stub native init ran).
    assert (dest / "pyproject.toml").is_file()

    # Mise sentinel written.
    assert (dest / ".clerk-python-mise-installed").is_file()


# --------------------------------------------------------------------------- #
# ruff strict profile                                                          #
# --------------------------------------------------------------------------- #


def test_ruff_strict_profile_adds_rules(clerk_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """ruff_rule_profile=strict adds ANN, RUF, PERF, C4, PT to the lint select list."""
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "uv",
            "python_version": "3.13",
            "python_layout": "src",
            "ruff_rule_profile": "strict",
            "ruff_line_length": "100",
            "ruff_quote_style": "single",
        },
    )
    runner.init(spec, today="2026-07-13")

    ruff_text = (dest / "ruff.toml").read_text()
    assert '"ANN"' in ruff_text, "strict profile missing ANN rule"
    assert '"RUF"' in ruff_text, "strict profile missing RUF rule"
    assert "line-length = 100" in ruff_text, "line-length not applied"
    assert 'quote-style = "single"' in ruff_text, "quote-style not applied"


# --------------------------------------------------------------------------- #
# python version threading: target-version matches chosen python_version        #
# --------------------------------------------------------------------------- #


def test_ruff_target_version_threaded_from_python_version(
    clerk_mod_python: TemplateRepo, tmp_path: Path
) -> None:
    """ruff target-version is threaded from python_version (not hardcoded)."""
    trust.add_trust(clerk_mod_python.url)

    for version, expected in [("3.11", "py311"), ("3.12", "py312"), ("3.14", "py314")]:
        dest = tmp_path / f"proj_{version}"
        spec = runner.RunSpec(
            source=clerk_mod_python.url,
            dest=str(dest),
            answers={
                "python_version": version,
                "python_pkg_manager": "uv",
                "python_layout": "src",
            },
        )
        runner.init(spec, today="2026-07-13")
        ruff_text = (dest / "ruff.toml").read_text()
        assert f'target-version = "{expected}"' in ruff_text, (
            f"python_version={version} did not produce target-version={expected}"
        )


# --------------------------------------------------------------------------- #
# pdm variant: pyproject present, sentinel written                             #
# --------------------------------------------------------------------------- #


def test_pdm_variant_pyproject_and_sentinel(
    clerk_mod_python_pdm: TemplateRepo, tmp_path: Path
) -> None:
    """pdm variant: pyproject.toml present (task-output stub), mise sentinel written."""
    trust.add_trust(clerk_mod_python_pdm.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python_pdm.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "pdm",
            "python_version": "3.13",
            "python_layout": "flat",
            "ruff_rule_profile": "standard",
        },
    )
    runner.init(spec, today="2026-07-13")

    assert (dest / "pyproject.toml").is_file(), "pyproject.toml missing (pdm variant)"
    assert (dest / ".clerk-python-mise-installed").is_file(), "mise sentinel missing (pdm)"
    assert (dest / "ruff.toml").is_file(), "ruff.toml missing (pdm variant)"


# --------------------------------------------------------------------------- #
# add_tests opt-in: tests/ + pytest.ini when true, absent when false          #
# --------------------------------------------------------------------------- #


def test_add_tests_true_creates_scaffold(clerk_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """add_tests=true: tests/test_example.py (seed-once) and pytest.ini (managed) created."""
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "uv",
            "python_version": "3.13",
            "python_layout": "src",
            "add_tests": True,
        },
    )
    runner.init(spec, today="2026-07-13")

    # SEED-ONCE: test_example.py scaffolded on init.
    assert (dest / "tests" / "test_example.py").is_file(), "tests/test_example.py missing"
    # MANAGED: pytest.ini present and contains testpaths.
    assert (dest / "pytest.ini").is_file(), "pytest.ini missing"
    assert "testpaths = tests" in (dest / "pytest.ini").read_text(), "pytest.ini missing testpaths"


def test_add_tests_false_no_scaffold(clerk_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """add_tests=false (default): tests/ and pytest.ini are NOT created."""
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "uv",
            "python_version": "3.13",
            "python_layout": "src",
            "add_tests": False,
        },
    )
    runner.init(spec, today="2026-07-13")

    assert not (dest / "pytest.ini").exists(), "pytest.ini should not exist when add_tests=false"
    # tests/ may exist from the base layer but test_example.py must not be present.
    assert not (dest / "tests" / "test_example.py").exists(), (
        "tests/test_example.py should not exist when add_tests=false"
    )


def test_add_tests_seed_once_not_clobbered(clerk_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """SEED-ONCE: tests/test_example.py is not overwritten on reproduce."""
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "uv",
            "python_version": "3.13",
            "python_layout": "src",
            "add_tests": True,
        },
    )
    runner.init(spec, today="2026-07-13")

    # Simulate project ownership: edit the example test.
    example = dest / "tests" / "test_example.py"
    custom_content = "# custom test\ndef test_real():\n    assert 1 + 1 == 2\n"
    example.write_text(custom_content)

    # Single-layer reproduce: the module has a run_after:clerk-mod-base edge so
    # reproduce_many would fail on a standalone project (no base answers file).
    # runner.reproduce drives the single answers file directly.
    # runner.init (single-layer) writes .copier-answers.yml, not the multi-layer name.
    runner.reproduce(str(dest))

    assert example.read_text() == custom_content, (
        "tests/test_example.py clobbered on reproduce (seed-once broken)"
    )


def test_add_tests_pytest_ini_managed(clerk_mod_python: TemplateRepo, tmp_path: Path) -> None:
    """MANAGED: pytest.ini is byte-identical after reproduce."""
    trust.add_trust(clerk_mod_python.url)

    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_python.url,
        dest=str(dest),
        answers={
            "python_pkg_manager": "uv",
            "python_version": "3.13",
            "python_layout": "src",
            "add_tests": True,
        },
    )
    runner.init(spec, today="2026-07-13")

    ini_before = _digest(dest / "pytest.ini")
    # Single-layer reproduce (same reason as test_add_tests_seed_once_not_clobbered).
    # runner.init (single-layer) writes .copier-answers.yml, not the multi-layer name.
    runner.reproduce(str(dest))
    assert _digest(dest / "pytest.ini") == ini_before, (
        "pytest.ini changed on reproduce (not managed)"
    )
