"""spec 011 T014: bailiff-mod-agentic loop tests.

Covers:
- Each target subset renders disjoint config files (no collision).
- Empty selection = clean no-op (only .copier-answers.yml written).
- R2 validator refuses install_via_apm=true + empty apm_packages.
- native_marketplace → manifests + (stubbed) plugin install.
- install_via_apm + kiro → apm path (stubbed offline).
- mcp_config → per-target MCP file with ${VAR} refs (no secret question).
- seed-once: .kiro/steering/project.md NOT overwritten on reproduce.
- AGENTIC.md always present (managed).

All tasks are stubbed offline via the bailiff_mod_agentic fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from bailiff.errors import InvalidRunSpecError
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(
    repo: TemplateRepo,
    dest: Path,
    answers: dict[str, object],
) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-14")


# --------------------------------------------------------------------------- #
# Empty selection: clean no-op                                                  #
# --------------------------------------------------------------------------- #


def test_empty_targets_clean_noop(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """Empty agentic_targets = only .copier-answers.yml written (no refusal, no error)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_agentic, dest, {"project_name": "myapp", "agentic_targets": []})

    assert dest.is_dir(), "dest not created"
    # Answers file always written.
    assert (dest / ".copier-answers.yml").is_file(), "answers file missing"
    # AGENTIC.md always written.
    assert (dest / "AGENTIC.md").is_file(), "AGENTIC.md missing"
    # No target-specific files.
    assert not (dest / ".claude").exists(), ".claude written on empty selection"
    assert not (dest / ".codex").exists(), ".codex written on empty selection"
    assert not (dest / "opencode.json").exists(), "opencode.json written on empty selection"
    assert not (dest / ".kiro").exists(), ".kiro written on empty selection"
    # No task-output files.
    assert not (dest / "apm.lock.yaml").exists(), "apm.lock.yaml written on empty selection"


# --------------------------------------------------------------------------- #
# R2: install_via_apm=true + empty apm_packages refused                        #
# --------------------------------------------------------------------------- #


def test_r2_apm_empty_packages_refused(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """R2: install_via_apm=true + apm_packages==[] is refused; no files written."""
    dest = tmp_path / "proj"
    trust.add_trust(bailiff_mod_agentic.url)
    spec = runner.RunSpec(
        source=bailiff_mod_agentic.url,
        dest=str(dest),
        answers={
            "project_name": "myapp",
            "agentic_targets": ["kiro"],
            "install_via_apm": True,
            "apm_packages": [],
        },
    )
    with pytest.raises(InvalidRunSpecError) as excinfo:
        runner.init(spec, today="2026-07-14")

    msg = str(excinfo.value)
    assert "install_via_apm" in msg or "R2" in msg or "apm_packages" in msg, (
        f"refusal message must reference install_via_apm/R2/apm_packages: {msg}"
    )


def test_r2_empty_targets_no_apm_is_ok(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """Empty targets + install_via_apm=false (default) is fine; NOT an R2 violation."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_agentic,
        dest,
        {"project_name": "myapp", "agentic_targets": [], "install_via_apm": False},
    )
    assert (dest / ".copier-answers.yml").is_file(), "answers file missing"


# --------------------------------------------------------------------------- #
# Claude target                                                                 #
# --------------------------------------------------------------------------- #


def test_claude_target_renders_settings(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """Claude target renders .claude/settings.json (managed)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_agentic, dest, {"project_name": "myapp", "agentic_targets": ["claude"]})

    settings_path = dest / ".claude" / "settings.json"
    assert settings_path.is_file(), ".claude/settings.json not rendered for claude target"

    data = yaml.safe_load(settings_path.read_text())  # JSON is valid YAML
    assert data["project"]["name"] == "myapp", "project name not in settings.json"

    # No other target files.
    assert not (dest / ".codex").exists(), ".codex created for claude-only selection"
    assert not (dest / "opencode.json").exists()
    assert not (dest / ".kiro").exists()


def test_claude_mcp_config_renders_mcp_json(
    bailiff_mod_agentic: TemplateRepo, tmp_path: Path
) -> None:
    """Claude + mcp_config renders .mcp.json with ${VAR} refs in env (no secret question)."""
    dest = tmp_path / "proj"
    servers = [
        {
            "name": "my-server",
            "command": "npx",
            "args": ["-y", "@myorg/mcp-server"],
            "env": {"API_KEY": "${MY_API_KEY}"},
        }
    ]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["claude"],
            "mcp_config": True,
            "mcp_servers": servers,
        },
    )

    mcp_path = dest / ".mcp.json"
    assert mcp_path.is_file(), ".mcp.json not rendered when mcp_config=true + claude"

    text = mcp_path.read_text()
    # Env value must use ${VAR} ref form, not a literal secret.
    assert "${MY_API_KEY}" in text, "env value not written as ${VAR} ref in .mcp.json"
    assert "my-server" in text, "server name missing from .mcp.json"


def test_claude_marketplace_renders_settings_with_plugins(
    bailiff_mod_agentic: TemplateRepo, tmp_path: Path
) -> None:
    """Claude + native_marketplace renders settings.json with extraKnownMarketplaces."""
    dest = tmp_path / "proj"
    plugins = [{"name": "my-plugin", "owner_repo": "myorg/my-plugin"}]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["claude"],
            "native_marketplace": True,
            "agentic_plugins": plugins,
        },
    )

    settings_path = dest / ".claude" / "settings.json"
    assert settings_path.is_file()
    text = settings_path.read_text()
    assert "extraKnownMarketplaces" in text, "extraKnownMarketplaces missing from settings"
    assert "my-plugin" in text, "plugin name missing from settings"
    assert "enabledPlugins" in text, "enabledPlugins missing from settings"

    # Stub plugin install task ran.
    assert (dest / ".bailiff-claude-plugin-install").is_file(), (
        "claude plugin install stub did not run"
    )


# --------------------------------------------------------------------------- #
# Codex target                                                                  #
# --------------------------------------------------------------------------- #


def test_codex_target_renders_config(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """Codex target renders .codex/config.toml (managed)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_agentic, dest, {"project_name": "myapp", "agentic_targets": ["codex"]})

    config_path = dest / ".codex" / "config.toml"
    assert config_path.is_file(), ".codex/config.toml not rendered for codex target"
    # No other target files.
    assert not (dest / ".claude").exists()
    assert not (dest / "opencode.json").exists()
    assert not (dest / ".kiro").exists()


def test_codex_marketplace_renders_manifest(
    bailiff_mod_agentic: TemplateRepo, tmp_path: Path
) -> None:
    """Codex + native_marketplace renders .agents/plugins/marketplace.json."""
    dest = tmp_path / "proj"
    plugins = [{"name": "my-plugin", "owner_repo": "myorg/my-plugin"}]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["codex"],
            "native_marketplace": True,
            "agentic_plugins": plugins,
        },
    )

    manifest_path = dest / ".agents" / "plugins" / "marketplace.json"
    assert manifest_path.is_file(), ".agents/plugins/marketplace.json not rendered"

    import json

    data = json.loads(manifest_path.read_text())
    assert any(p["name"] == "my-plugin" for p in data["plugins"])


# --------------------------------------------------------------------------- #
# OpenCode target                                                               #
# --------------------------------------------------------------------------- #


def test_opencode_target_renders_config(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """OpenCode target renders opencode.json (managed)."""
    dest = tmp_path / "proj"
    plugins = [{"name": "my-plugin", "owner_repo": "myorg/my-plugin@1.0.0"}]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["opencode"],
            "agentic_plugins": plugins,
        },
    )

    config_path = dest / "opencode.json"
    assert config_path.is_file(), "opencode.json not rendered for opencode target"
    text = config_path.read_text()
    assert "my-plugin" in text, "plugin name missing from opencode.json"
    # No other target files.
    assert not (dest / ".claude").exists()
    assert not (dest / ".codex").exists()
    assert not (dest / ".kiro").exists()


# --------------------------------------------------------------------------- #
# Kiro target                                                                   #
# --------------------------------------------------------------------------- #


def test_kiro_target_renders_steering_seed_once(
    bailiff_mod_agentic: TemplateRepo, tmp_path: Path
) -> None:
    """Kiro target renders .kiro/steering/project.md as seed-once (not overwritten)."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_agentic, dest, {"project_name": "myapp", "agentic_targets": ["kiro"]})

    steering_path = dest / ".kiro" / "steering" / "project.md"
    assert steering_path.is_file(), ".kiro/steering/project.md not rendered for kiro target"

    # Edit it (simulating project customisation).
    steering_path.write_text("# My Custom Steering\n")

    # Reproduce — seed-once means it must NOT be overwritten.
    runner.reproduce_many(str(dest))

    assert steering_path.read_text() == "# My Custom Steering\n", (
        ".kiro/steering/project.md was overwritten on reproduce (must be seed-once)"
    )


def test_kiro_mcp_config_renders_mcp_json(
    bailiff_mod_agentic: TemplateRepo, tmp_path: Path
) -> None:
    """Kiro + mcp_config renders .kiro/settings/mcp.json (managed)."""
    dest = tmp_path / "proj"
    servers = [{"name": "kiro-server", "command": "kiro-mcp", "args": []}]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["kiro"],
            "mcp_config": True,
            "mcp_servers": servers,
        },
    )

    mcp_path = dest / ".kiro" / "settings" / "mcp.json"
    assert mcp_path.is_file(), ".kiro/settings/mcp.json not rendered for kiro + mcp_config"
    assert "kiro-server" in mcp_path.read_text()


def test_kiro_cli_agents_renders_agents_json(
    bailiff_mod_agentic: TemplateRepo, tmp_path: Path
) -> None:
    """Kiro + kiro_cli_agents=true renders .kiro/agents/agents.json (managed)."""
    dest = tmp_path / "proj"
    plugins = [{"name": "my-agent", "owner_repo": "myorg/my-agent"}]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["kiro"],
            "kiro_cli_agents": True,
            "agentic_plugins": plugins,
        },
    )

    agents_path = dest / ".kiro" / "agents" / "agents.json"
    assert agents_path.is_file(), ".kiro/agents/agents.json not rendered when kiro_cli_agents=true"
    assert "my-agent" in agents_path.read_text()


def test_kiro_apm_path_stubbed(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """Kiro + install_via_apm + non-empty apm_packages writes apm.lock.yaml (task-output)."""
    dest = tmp_path / "proj"
    pkgs = ["srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0"]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["kiro"],
            "install_via_apm": True,
            "apm_packages": pkgs,
        },
    )

    assert (dest / ".bailiff-agentic-preflight").is_file(), "agentic preflight stub not run"
    assert (dest / "apm.lock.yaml").is_file(), "apm install stub did not write lock"


# --------------------------------------------------------------------------- #
# Multi-target: disjoint paths, no collision                                    #
# --------------------------------------------------------------------------- #


def test_multi_target_all_disjoint(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """All four targets selected → each config on disjoint paths, no collision."""
    dest = tmp_path / "proj"
    servers = [{"name": "srv", "command": "npx", "args": ["-y", "srv-mcp"]}]
    _init(
        bailiff_mod_agentic,
        dest,
        {
            "project_name": "myapp",
            "agentic_targets": ["claude", "codex", "opencode", "kiro"],
            "mcp_config": True,
            "mcp_servers": servers,
        },
    )

    assert (dest / ".claude" / "settings.json").is_file(), "claude settings missing"
    assert (dest / ".mcp.json").is_file(), ".mcp.json missing"
    assert (dest / ".codex" / "config.toml").is_file(), "codex config missing"
    assert (dest / "opencode.json").is_file(), "opencode.json missing"
    assert (dest / ".kiro" / "settings" / "mcp.json").is_file(), "kiro mcp.json missing"
    assert (dest / ".kiro" / "steering" / "project.md").is_file(), "kiro steering missing"

    # Verify answers recorded.
    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert set(af["agentic_targets"]) == {"claude", "codex", "opencode", "kiro"}


def test_claude_codex_only_disjoint(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """Claude + Codex only — no opencode.json or .kiro/ created."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_agentic,
        dest,
        {"project_name": "myapp", "agentic_targets": ["claude", "codex"]},
    )

    assert (dest / ".claude" / "settings.json").is_file()
    assert (dest / ".codex" / "config.toml").is_file()
    assert not (dest / "opencode.json").exists()
    assert not (dest / ".kiro").exists()


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# --------------------------------------------------------------------------- #
# AGENTIC.md always present                                                     #
# --------------------------------------------------------------------------- #


def test_agentic_md_present_all_targets(bailiff_mod_agentic: TemplateRepo, tmp_path: Path) -> None:
    """AGENTIC.md is always written regardless of target selection."""
    for targets in [[], ["claude"], ["codex"], ["kiro"], ["claude", "codex", "kiro"]]:
        dest = tmp_path / f"proj-{'_'.join(targets) or 'empty'}"
        _init(
            bailiff_mod_agentic,
            dest,
            {"project_name": "myapp", "agentic_targets": targets},
        )
        assert (dest / "AGENTIC.md").is_file(), f"AGENTIC.md missing for targets={targets}"
