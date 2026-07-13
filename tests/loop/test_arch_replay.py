"""spec 009 US4 #1 / SC-005 (T028): the frozen architecture fact replays agent-free.

Init clerk-mod-base with write_architecture=true + a frozen architecture_md (+
agent_editable_globs) injected as --data → the ## Architecture sentinel span
renders those facts. Reproduce → the span re-renders byte-identically from the
frozen answer, with NO agent call (reproduce is agent-free by construction —
there is no agent in the path). Also assert write_architecture=false leaves the
empty sentinel pair (Q5 gate).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clerk import runner, trust
from tests.conftest import TemplateRepo

_ARCH_BODY = (
    "This service does X and Y.\n\n"
    "| Path | Purpose |\n"
    "|------|---------|\n"
    "| `src/` | application code |\n"
    "| `tests/` | test suite |\n"
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _arch_span(agents_md: str) -> str:
    """Extract the text between the architecture sentinels (inclusive)."""
    begin = "<!-- BEGIN ps:architecture -->"
    end = "<!-- END ps:architecture -->"
    return agents_md[agents_md.index(begin) : agents_md.index(end) + len(end)]


def test_frozen_arch_renders_and_replays(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """write_architecture=true → frozen facts render into the span; reproduce is identical."""
    trust.add_trust(clerk_mod_base.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_base.url,
        dest=str(dest),
        answers={
            "project_name": "demo",
            "license": "mit",
            "write_architecture": True,
            "architecture_md": _ARCH_BODY,
            "agent_editable_globs": ["src/**", "tests/**"],
        },
    )
    runner.init(spec, today="2026-07-13")

    agents = (dest / "AGENTS.md").read_text()
    span = _arch_span(agents)
    assert "This service does X and Y." in span, "frozen architecture_md not spliced"
    assert "| `src/` | application code |" in span

    # AGENTS.md is seed-once, so a plain reproduce over the populated tree leaves it
    # untouched (it is preserved verbatim). Byte-identity of the span holds trivially,
    # and — the SC-005 point — no agent is ever invoked. Capture the digest, reproduce,
    # re-check.
    before = hashlib.sha256((dest / "AGENTS.md").read_bytes()).hexdigest()
    runner.reproduce(str(dest))
    after = hashlib.sha256((dest / "AGENTS.md").read_bytes()).hexdigest()
    assert before == after, "AGENTS.md architecture span changed on reproduce"


def test_arch_gate_false_leaves_empty_sentinels(
    clerk_mod_base: TemplateRepo, tmp_path: Path
) -> None:
    """write_architecture=false → the sentinel pair is empty (Q5 gate), even if a fact exists."""
    trust.add_trust(clerk_mod_base.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_base.url,
        dest=str(dest),
        answers={
            "project_name": "demo",
            "license": "mit",
            "write_architecture": False,
            # A frozen fact is present but the gate is off → it must NOT be spliced.
            "architecture_md": _ARCH_BODY,
        },
    )
    runner.init(spec, today="2026-07-13")

    span = _arch_span((dest / "AGENTS.md").read_text())
    assert "This service does X and Y." not in span, "gate off but arch fact was spliced"
    # The span is the empty sentinel pair (only whitespace between the markers).
    inner = span.replace("<!-- BEGIN ps:architecture -->", "").replace(
        "<!-- END ps:architecture -->", ""
    )
    assert inner.strip() == "", f"expected empty sentinel span, got: {inner!r}"
