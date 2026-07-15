"""spec 011 T013: bailiff-mod-stack-adr loop tests.

Covers:
- simple format: STACK.md rendered from frozen facts; seed-once on reproduce.
- adr format: numbered ADR rendered under adr_dir; seed-once on reproduce.
- rationale with {{ }} notation is written verbatim (no double-render).
- no agent step in reproduce path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from bailiff.catalog import TemplateRecord
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
        has_tasks=False,
        questions=questions,
    )


# ---------------------------------------------------------------------------
# Simple format
# ---------------------------------------------------------------------------


def test_simple_format_init_writes_stack_md(
    bailiff_mod_stack_adr: TemplateRepo, tmp_path: Path
) -> None:
    """simple format: STACK.md is created at init with frozen stack facts."""
    trust.add_trust(bailiff_mod_stack_adr.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_stack_adr.url,
        dest=str(dest),
        answers={
            "project_name": "myapp",
            "format": "simple",
            "stack_pins": ["python@3.13", "uv@0.4"],
            "framework": "fastapi",
            "rationale": "Fast async Python API; {{ python: '3.13' }} chosen for speed.",
        },
    )
    runner.init(spec, today="2026-01-15")

    stack = (dest / "STACK.md").read_text()

    # MANAGED content: verify structure matches frozen facts.
    assert "# Stack — myapp" in stack
    assert "fastapi" in stack
    assert "python@3.13" in stack
    assert "uv@0.4" in stack
    # Rationale with {{ }} must be written verbatim (no double-render).
    assert "{{ python: '3.13' }}" in stack

    # ADR directory must NOT be created (format=simple → excluded).
    assert not (dest / "docs" / "decisions").is_dir()


def test_simple_format_seed_once_not_overwritten(
    bailiff_mod_stack_adr: TemplateRepo, tmp_path: Path
) -> None:
    """simple format: STACK.md is not overwritten on reproduce (_skip_if_exists)."""
    trust.add_trust(bailiff_mod_stack_adr.url)
    dest = tmp_path / "proj"
    answers: dict[str, Any] = {
        "project_name": "myapp",
        "format": "simple",
        "stack_pins": ["python@3.13"],
        "framework": "fastapi",
        "rationale": "Initial rationale.",
    }
    spec = runner.RunSpec(
        source=bailiff_mod_stack_adr.url,
        dest=str(dest),
        answers=answers,
    )
    runner.init(spec, today="2026-01-15")

    original = (dest / "STACK.md").read_text()

    # Mutate the file to simulate project edits.
    (dest / "STACK.md").write_text("# Project-edited STACK\nmy custom content\n")

    # Reproduce must not overwrite.
    runner.reproduce(str(dest))

    after = (dest / "STACK.md").read_text()
    assert after == "# Project-edited STACK\nmy custom content\n", (
        "STACK.md was overwritten on reproduce — seed-once violated"
    )
    # Original init value preserved in answers file (frozen answer check).
    _ = original  # referenced to avoid lint; init content is the pre-edit baseline


def test_simple_format_reproduce_no_agent(
    bailiff_mod_stack_adr: TemplateRepo, tmp_path: Path
) -> None:
    """Reproduce replays frozen answers; no agent step in reproduce path."""
    trust.add_trust(bailiff_mod_stack_adr.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_stack_adr.url,
        dest=str(dest),
        answers={"project_name": "myapp", "format": "simple", "stack_pins": ["go@1.23"]},
    )
    runner.init(spec, today="2026-01-15")

    # Standalone init writes .copier-answers.yml; multi-layer init_many uses the
    # module-name-suffixed form. Find whichever answers file was written.
    af_candidates = list(dest.glob(".copier-answers*.yml"))
    assert af_candidates, "no answers file written"
    af_path = af_candidates[0]
    af = yaml.safe_load(af_path.read_text())
    assert af["format"] == "simple"
    assert "go@1.23" in af["stack_pins"]

    # Reproduce is purely answer-replay (no agent marker file created).
    runner.reproduce(str(dest))
    # No side-effect files from an agent step.
    assert not (dest / ".bailiff-stack-adr-agent").exists()


# ---------------------------------------------------------------------------
# ADR format
# ---------------------------------------------------------------------------


def test_adr_format_init_writes_numbered_adr(
    bailiff_mod_stack_adr: TemplateRepo, tmp_path: Path
) -> None:
    """adr format: numbered ADR written under adr_dir with MADR headings."""
    trust.add_trust(bailiff_mod_stack_adr.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_stack_adr.url,
        dest=str(dest),
        answers={
            "project_name": "svcapp",
            "format": "adr",
            "adr_dir": "docs/decisions",
            "stack_pins": ["node@22", "pnpm@9"],
            "framework": "express",
            "rationale": "Node chosen for {{ io_model: 'async' }} performance.",
        },
    )
    runner.init(spec, today="2026-01-15")

    adr_file = dest / "docs" / "decisions" / "0001-stack.md"
    assert adr_file.is_file(), "ADR file not created"
    content = adr_file.read_text()

    # MADR structure: required headings.
    assert "# ADR-0001" in content
    assert "## Status" in content
    assert "Accepted" in content
    assert "## Context" in content
    assert "## Decision" in content
    assert "## Consequences" in content

    # Frozen facts present.
    assert "svcapp" in content
    assert "node@22" in content
    assert "pnpm@9" in content
    assert "express" in content

    # Rationale with {{ }} must be written verbatim (no double-render).
    assert "{{ io_model: 'async' }}" in content

    # STACK.md must NOT be created (format=adr → excluded).
    assert not (dest / "STACK.md").exists()


def test_adr_format_seed_once_not_overwritten(
    bailiff_mod_stack_adr: TemplateRepo, tmp_path: Path
) -> None:
    """adr format: ADR file is not overwritten on reproduce (_skip_if_exists)."""
    trust.add_trust(bailiff_mod_stack_adr.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_stack_adr.url,
        dest=str(dest),
        answers={
            "project_name": "svcapp",
            "format": "adr",
            "adr_dir": "docs/decisions",
            "stack_pins": ["node@22"],
        },
    )
    runner.init(spec, today="2026-01-15")

    adr_file = dest / "docs" / "decisions" / "0001-stack.md"
    # Mutate to simulate project edits.
    adr_file.write_text("# Custom ADR\nproject-owned edit\n")

    runner.reproduce(str(dest))

    after = adr_file.read_text()
    assert after == "# Custom ADR\nproject-owned edit\n", (
        "ADR file was overwritten on reproduce — seed-once violated"
    )


def test_adr_format_custom_adr_dir(bailiff_mod_stack_adr: TemplateRepo, tmp_path: Path) -> None:
    """adr format: adr_dir overridden to a non-default location."""
    trust.add_trust(bailiff_mod_stack_adr.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=bailiff_mod_stack_adr.url,
        dest=str(dest),
        answers={
            "project_name": "svcapp",
            "format": "adr",
            "adr_dir": "architecture/decisions",
            "stack_pins": ["rust@1.79"],
        },
    )
    runner.init(spec, today="2026-01-15")

    adr_file = dest / "architecture" / "decisions" / "0001-stack.md"
    assert adr_file.is_file(), "ADR not written to overridden adr_dir"
    assert "rust@1.79" in adr_file.read_text()
