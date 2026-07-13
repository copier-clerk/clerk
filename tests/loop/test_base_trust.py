"""spec 009 US1 #2 / SC-004 (T018): an untrusted clerk-mod-base is refused.

Init an UNTRUSTED clerk-mod-base source → clerk refuses at exit 3 naming the
`trust add` command, BEFORE any `_task` runs (no .git, no LICENSE written). The
module has `_tasks` (code execution), so the source-trust gate applies (Q5:
execution stays behind the single source-trust gate).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from clerk import runner, trust
from clerk.errors import UntrustedSourceError
from tests.conftest import TemplateRepo

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "clerk.py"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_untrusted_base_refused_before_tasks(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """Untrusted base → UntrustedSourceError with a prefix; no task side-effects."""
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_base.url,
        dest=str(dest),
        answers={"project_name": "demo", "license": "mit"},
    )

    with pytest.raises(UntrustedSourceError) as excinfo:
        runner.init(spec, today="2026-07-13")

    assert excinfo.value.prefix, "refusal must name a prefix to trust"
    # No consequential task ran: no LICENSE, no .git.
    assert not (dest / "LICENSE").exists() if dest.exists() else True
    assert not (dest / ".git").exists() if dest.exists() else True
    # The failed run must not have recorded trust itself (FR-019).
    assert trust.list_trust() == []


def test_untrusted_base_cli_exits_3(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """scripts/clerk.py init exits 3 for the untrusted base source (SC-004)."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {
                "source": clerk_mod_base.url,
                "dest": str(dest),
                "answers": {"project_name": "demo", "license": "mit"},
            }
        )
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "init", "--run-spec", str(run_spec)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 3, f"expected exit 3, got {result.returncode}: {result.stderr}"
    assert result.stderr.strip(), "refusal must print an error (not a bare stack trace)"
    assert not (dest / "LICENSE").exists() if dest.exists() else True


def test_trusted_base_then_init_succeeds(clerk_mod_base: TemplateRepo, tmp_path: Path) -> None:
    """After trust is recorded, the same base init succeeds and runs its tasks."""
    trust.add_trust(clerk_mod_base.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_base.url,
        dest=str(dest),
        answers={"project_name": "demo", "license": "mit"},
    )
    runner.init(spec, today="2026-07-13")
    assert (dest / "LICENSE").is_file()
    assert (dest / ".git").is_dir()
