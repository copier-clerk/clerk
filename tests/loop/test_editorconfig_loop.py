"""spec 012 T004 / spec 014 T040: bailiff-mod-editorconfig loop tests (FR-006).

Pure MANAGED render — zero _tasks. Assertions:
- init alone (no ts facts) → universal defaults only, no language sections;
- ts_linter=biome (via _external_data.ts) → TS section with 2-space indent;
- ts_linter=eslint-prettier (via _external_data.ts) → TS section with 2-space indent;
- python facts + ruff_line_length=88 → Python section max_line_length=88, indent 4
  (indentation from the linter convention, NEVER from line width);
- spec 014: _external_data.ts alias declared, ts_linter default uses the alias path;
- no secret: questions.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import (
    _MODULES_DIR,
    TemplateRepo,
    _git,
)

_EC_FILE = Path(".editorconfig")

# Name of the ts answers file that editorconfig reads via _external_data.
_TS_ANSWERS_FILE = ".copier-answers.bailiff-mod-ts.yml"

_UNIVERSAL_LINES = [
    "charset = utf-8",
    "end_of_line = lf",
    "insert_final_newline = true",
    "trim_trailing_whitespace = true",
]


def _copy_editorconfig_module(tmp_path: Path) -> TemplateRepo:
    """Clone the real bailiff-mod-editorconfig tree (pure render — no tasks to stub)."""
    src = _MODULES_DIR / "bailiff-mod-editorconfig"
    dest_root = tmp_path / "bailiff-mod-editorconfig"
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)
    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", "v1.0.0")
    return TemplateRepo(path=dest_root, tag="v1.0.0")


@pytest.fixture
def bailiff_mod_editorconfig(tmp_path: Path) -> TemplateRepo:
    return _copy_editorconfig_module(tmp_path)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _seed_ts_answers(dest: Path, ts_linter: str = "") -> None:
    """Write a minimal ts answers file so _external_data.ts resolves in tests.

    In a real stack ts runs first; in standalone editorconfig tests we pre-seed
    the file that copier would otherwise warn-and-skip (returning {}).
    """
    dest.mkdir(parents=True, exist_ok=True)
    answers = {
        "_src_path": "bailiff-mod-ts",
        "ts_linter": ts_linter,
    }
    (dest / _TS_ANSWERS_FILE).write_text(yaml.dump(answers))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> str:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")
    ec = dest / _EC_FILE
    assert ec.is_file(), ".editorconfig not rendered"
    return ec.read_text()


# ---------------------------------------------------------------------------
# Universal defaults only (US9 AS1, edge case: no language modules)
# ---------------------------------------------------------------------------


def test_universal_defaults_only(bailiff_mod_editorconfig: TemplateRepo, tmp_path: Path) -> None:
    """No ts facts → universal section only, no language sections invented."""
    dest = tmp_path / "proj"
    _seed_ts_answers(dest, ts_linter="")
    text = _init(bailiff_mod_editorconfig, dest, {})

    assert "root = true" in text
    for line in _UNIVERSAL_LINES:
        assert line in text, f"universal default missing: {line}"
    assert "[*.py]" not in text, "Python section invented without frozen facts"
    assert "[*.{js" not in text, "TS section invented without frozen facts"


# ---------------------------------------------------------------------------
# TS section from ts_linter convention (US9 AS1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("linter", ["biome", "eslint-prettier"])
def test_ts_section_from_linter_convention(
    bailiff_mod_editorconfig: TemplateRepo, tmp_path: Path, linter: str
) -> None:
    """ts_linter from _external_data.ts → TS section uses the linter's 2-space indent convention."""
    dest = tmp_path / "proj"
    _seed_ts_answers(dest, ts_linter=linter)
    text = _init(bailiff_mod_editorconfig, dest, {})

    ts_section = text.split("[*.{js")[1]
    assert "indent_style = space" in ts_section
    assert "indent_size = 2" in ts_section, f"{linter} convention is 2-space indent"
    # Line width facts never leak into indentation decisions.
    assert "max_line_length" not in ts_section


# ---------------------------------------------------------------------------
# Python section: indent from convention, max_line_length from ruff (US9 AS2)
# ---------------------------------------------------------------------------


def test_python_section_indent_and_line_length(
    bailiff_mod_editorconfig: TemplateRepo, tmp_path: Path
) -> None:
    """python facts frozen → indent 4 (ruff/PEP8 convention) + max_line_length=ruff_line_length."""
    dest = tmp_path / "proj"
    _seed_ts_answers(dest, ts_linter="")
    text = _init(
        bailiff_mod_editorconfig,
        dest,
        {"python_linter": "ruff", "ruff_line_length": "88"},
    )

    assert "[*.py]" in text
    py_section = text.split("[*.py]")[1]
    assert "indent_size = 4" in py_section, "Python indent is the linter convention (4)"
    assert "max_line_length = 88" in py_section

    # Different line length changes ONLY max_line_length, never the indent.
    dest_120 = tmp_path / "proj120"
    _seed_ts_answers(dest_120, ts_linter="")
    text_120 = _init(
        bailiff_mod_editorconfig,
        dest_120,
        {"python_linter": "ruff", "ruff_line_length": "120"},
    )
    py_120 = text_120.split("[*.py]")[1]
    assert "max_line_length = 120" in py_120
    assert "indent_size = 4" in py_120, "indentation must never derive from line width"


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# spec 014: _external_data alias declared (FR-004 / T040)
# ---------------------------------------------------------------------------


def test_external_data_alias_declared() -> None:
    """copier.yml declares _external_data.ts pointing at the ts answers file (FR-006a)."""
    copier_yml = _MODULES_DIR / "bailiff-mod-editorconfig" / "copier.yml"
    text = copier_yml.read_text()
    assert "_external_data:" in text
    data = yaml.safe_load(text)
    ext = data.get("_external_data", {})
    assert "ts" in ext, "_external_data.ts alias missing"
    assert ext["ts"] == ".copier-answers.bailiff-mod-ts.yml", (
        "ts alias must point to the literal answers file (FR-006a)"
    )


def test_ts_linter_default_uses_external_data_path() -> None:
    """ts_linter default references _external_data.ts.ts_linter (not the bare threaded key)."""
    copier_yml = _MODULES_DIR / "bailiff-mod-editorconfig" / "copier.yml"
    text = copier_yml.read_text()
    assert "{{ _external_data.ts.ts_linter }}" in text, (
        "ts_linter default must use _external_data.ts.ts_linter (FR-006a)"
    )
    assert 'default: "{{ ts_linter }}"' not in text, (
        "bare threaded {{ ts_linter }} default must be removed (spec 014 T040)"
    )


def test_depends_on_ts_not_run_after() -> None:
    """depends_on includes bailiff-mod-ts; run_after and run_before are absent (spec 014 R7)."""
    copier_yml = _MODULES_DIR / "bailiff-mod-editorconfig" / "copier.yml"
    text = copier_yml.read_text()
    data = yaml.safe_load(text)
    deps = data.get("depends_on", {}).get("default", [])
    assert "bailiff-mod-ts" in deps, "depends_on must include bailiff-mod-ts"
    assert "run_after" not in data, "run_after must be removed (spec 014 R7)"
    assert "run_before" not in data, "run_before must be removed (spec 014 R7)"


# ---------------------------------------------------------------------------
# Contract: no secret: questions
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    copier_yml = _MODULES_DIR / "bailiff-mod-editorconfig" / "copier.yml"
    text = copier_yml.read_text()
    assert not re.search(r"^\s+secret\s*:", text, re.MULTILINE), "secret: question found"
