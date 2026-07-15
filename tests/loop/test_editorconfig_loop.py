"""spec 012 T004: bailiff-mod-editorconfig loop tests (FR-006).

Pure MANAGED render — zero _tasks. Assertions:
- init alone (no language facts) → universal defaults only, no language sections;
- ts_linter=biome frozen → TS section with the linter's 2-space indent convention;
- python facts + ruff_line_length=88 → Python section max_line_length=88, indent 4
  (indentation from the linter convention, NEVER from line width);
- byte-identical on init AND reproduce (managed lifecycle);
- no secret: questions.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
from tests.conftest import (
    _BASE_STUB_TASKS,
    _MODULES_DIR,
    TemplateRepo,
    _copy_module_with_stub_tasks,
    _git,
)

_EC_FILE = Path(".editorconfig")

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


@pytest.fixture
def bailiff_mod_base(tmp_path: Path) -> TemplateRepo:
    return _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(full_id: str, repo: TemplateRepo, questions: list[str]) -> TemplateRecord:
    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=questions,
    )


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
    """No frozen language facts → universal section only, no language sections invented."""
    text = _init(bailiff_mod_editorconfig, tmp_path / "proj", {"ts_linter": ""})

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
    """ts_linter frozen → TS section uses the linter's 2-space indent convention."""
    text = _init(bailiff_mod_editorconfig, tmp_path / "proj", {"ts_linter": linter})

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
    text = _init(
        bailiff_mod_editorconfig,
        tmp_path / "proj",
        {"ts_linter": "", "python_linter": "ruff", "ruff_line_length": "88"},
    )

    assert "[*.py]" in text
    py_section = text.split("[*.py]")[1]
    assert "indent_size = 4" in py_section, "Python indent is the linter convention (4)"
    assert "max_line_length = 88" in py_section

    # Different line length changes ONLY max_line_length, never the indent.
    text_120 = _init(
        bailiff_mod_editorconfig,
        tmp_path / "proj120",
        {"ts_linter": "", "python_linter": "ruff", "ruff_line_length": "120"},
    )
    py_120 = text_120.split("[*.py]")[1]
    assert "max_line_length = 120" in py_120
    assert "indent_size = 4" in py_120, "indentation must never derive from line width"


# ---------------------------------------------------------------------------
# Reproduce: byte-identical managed render (US9 AS3)
# ---------------------------------------------------------------------------


def test_editorconfig_byte_identical_on_reproduce(
    bailiff_mod_base: TemplateRepo,
    bailiff_mod_editorconfig: TemplateRepo,
    tmp_path: Path,
) -> None:
    """Managed render is byte-identical after reproduce, no task executed."""
    trust.add_trust(bailiff_mod_base.url)
    trust.add_trust(bailiff_mod_editorconfig.url)

    selection: list[tuple[TemplateRecord, dict[str, Any]]] = [
        (
            _record("demo/bailiff-mod-base", bailiff_mod_base, ["project_name"]),
            {
                "project_name": "myapp",
                "org": "acme",
                "license": "mit",
                "layout": "single",
                "gitignore_stack": [],
            },
        ),
        (
            _record("demo/bailiff-mod-editorconfig", bailiff_mod_editorconfig, ["ts_linter"]),
            {"ts_linter": "biome", "python_linter": "ruff", "ruff_line_length": "88"},
        ),
    ]
    dest = tmp_path / "proj"
    runner.init_many(selection, str(dest), today="2026-07-14")

    ec = dest / _EC_FILE
    assert ec.is_file()
    before = _digest(ec)

    runner.reproduce_many(str(dest))

    assert _digest(ec) == before, ".editorconfig changed on reproduce"


# ---------------------------------------------------------------------------
# Contract: no secret: questions
# ---------------------------------------------------------------------------


def test_no_secret_questions() -> None:
    copier_yml = _MODULES_DIR / "bailiff-mod-editorconfig" / "copier.yml"
    text = copier_yml.read_text()
    assert not re.search(r"^\s+secret\s*:", text, re.MULTILINE), "secret: question found"
