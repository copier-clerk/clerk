"""Reusable REAL end-to-end harness for the bailiff-mod-* family — NO stubs.

Unlike tests/loop/ (hermetic, tasks stubbed), this harness runs the modules'
REAL trust-gated tasks: mise install, uv init, bun init, cargo init, go mod
init, gitnr, gh Licenses API. It therefore needs network + native toolchains
and is NOT collected by pytest (no test_ prefix; excluded from CI).

Usage (from the repo root, venv active):
    export GITHUB_TOKEN=$(gh auth token)      # mise attestation + gh API rate limits
    export BAILIFF_E2E_ROOT=/tmp/bailiff-e2e-$USER-1   # per-agent isolation
    uv run python -c "from tests.e2e.harness import *; ..."

Known answer-shape quirks (E2E-verified 2026-07-14):
- ``mise_tools`` is a LIST of single-key maps: ``[{"python": "3.13"}, {"uv": "0.11.8"}]``
- ``gitignore_stack`` tokens are capitalized gitnr short-codes: Python, Node, Go, Rust
- ``hook_blocks`` / ``quality_languages`` are agent-frozen unions (lists), default []
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
E2E = Path(os.environ.get("BAILIFF_E2E_ROOT", "/tmp/bailiff-e2e"))
MODULES_SRC = REPO / "templates"

sys.path.insert(0, str(REPO / "src"))

from bailiff import runner, trust  # noqa: E402
from bailiff.catalog import TemplateRecord  # noqa: E402
from bailiff.errors import BailiffError  # noqa: E402

__all__ = [
    "BailiffError",
    "check",
    "expect_failure",
    "make_module_repo",
    "record",
    "run_scenario",
    "runner",
]


def _sh(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def make_module_repo(name: str) -> str:
    """Copy the REAL module (real _tasks) into a tagged git repo; return its path/URL."""
    dest = E2E / "modules" / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(MODULES_SRC / name, dest)
    _sh("git", "init", "-q", cwd=dest)
    _sh("git", "add", "-A", cwd=dest)
    _sh(
        "git",
        "-c",
        "user.email=e2e@test",
        "-c",
        "user.name=e2e",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "module",
        cwd=dest,
    )
    _sh("git", "tag", "v1.0.0", cwd=dest)
    return str(dest)


def record(name: str, url: str) -> TemplateRecord:
    return TemplateRecord(
        full_id=f"e2e/{name}",
        source=url,
        ref="v1.0.0",
        versions=["v1.0.0"],
        reproducible=True,
        has_tasks=True,
        questions=[],
    )


def _trust_with_retry(url: str, attempts: int = 3) -> None:
    # The trust store is a shared file; parallel harness roots can race on the
    # read-modify-write. Verify after adding and retry.
    for _ in range(attempts):
        trust.add_trust(url)
        try:
            if trust.is_trusted(url):
                return
        except AttributeError:  # older trust API — add_trust alone suffices
            return
        time.sleep(0.2)


def run_scenario(scenario: str, module_answers: list[tuple[str, dict]]) -> Path:
    """Init a fresh project at E2E/projects/<scenario> from real modules. Returns dest."""
    dest = E2E / "projects" / scenario
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    selection = []
    for name, answers in module_answers:
        url = make_module_repo(name)
        _trust_with_retry(url)
        selection.append((record(name, url), answers))

    runner.init_many(selection, str(dest), today="2026-07-14")
    return dest


def expect_failure(
    scenario: str,
    module_answers: list[tuple[str, dict]],
    match: str = "",
) -> tuple[bool, str]:
    """Run a scenario that SHOULD fail. Returns (failed_as_expected, message)."""
    try:
        run_scenario(scenario, module_answers)
        return False, f"{scenario}: expected failure but init SUCCEEDED"
    except (BailiffError, RuntimeError) as exc:
        msg = str(exc)
        if match and match.lower() not in msg.lower():
            return False, f"{scenario}: failed but message lacks {match!r}: {msg[:300]}"
        return True, f"{scenario}: failed loudly as expected"


def check(cond: bool, msg: str, failures: list[str]) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        failures.append(msg)
