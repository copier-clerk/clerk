"""spec 007 US1 #2 / SC-004 (T012): an untrusted clerk-mod-apm is refused at exit 3.

Init an UNTRUSTED clerk-mod-apm source → clerk refuses at exit 3 naming the
`trust add` command, BEFORE any `_task` runs (no apm.yml install side-effects).
The module has `_tasks` (code execution), so the source-trust gate applies.
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
_PKGS = ["srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0"]


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_untrusted_apm_refused_before_tasks(clerk_mod_apm: TemplateRepo, tmp_path: Path) -> None:
    """Untrusted apm → UntrustedSourceError naming a prefix; no task side-effects."""
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_apm.url,
        dest=str(dest),
        answers={"project_name": "myapp", "apm_packages": _PKGS},
    )

    with pytest.raises(UntrustedSourceError) as excinfo:
        runner.init(spec, today="2026-07-13")

    assert excinfo.value.prefix, "refusal must name a prefix to trust"
    # No consequential task ran: no lock, no preflight marker written.
    assert not (dest / "apm.lock.yaml").exists() if dest.exists() else True
    assert not (dest / ".clerk-apm-preflight").exists() if dest.exists() else True
    # The failed run must not have recorded trust itself.
    assert trust.list_trust() == []


def test_untrusted_apm_cli_exits_3(clerk_mod_apm: TemplateRepo, tmp_path: Path) -> None:
    """scripts/clerk.py init exits 3 for the untrusted apm source (SC-004)."""
    settings_path = tmp_path / "settings.yml"
    env = {**os.environ, "COPIER_SETTINGS_PATH": str(settings_path)}

    dest = tmp_path / "proj"
    run_spec = tmp_path / "run_spec.json"
    run_spec.write_text(
        json.dumps(
            {
                "source": clerk_mod_apm.url,
                "dest": str(dest),
                "answers": {"project_name": "myapp", "apm_packages": _PKGS},
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
    assert "trust add" in result.stderr, "refusal must name the trust add command"
    assert not (dest / "apm.lock.yaml").exists() if dest.exists() else True


def test_trusted_apm_then_init_succeeds(clerk_mod_apm: TemplateRepo, tmp_path: Path) -> None:
    """After trust is recorded, the same apm init succeeds and runs its tasks."""
    trust.add_trust(clerk_mod_apm.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=clerk_mod_apm.url,
        dest=str(dest),
        answers={"project_name": "myapp", "apm_packages": _PKGS},
    )
    runner.init(spec, today="2026-07-13")
    assert (dest / "apm.yml").is_file()
    assert (dest / "apm.lock.yaml").is_file()
