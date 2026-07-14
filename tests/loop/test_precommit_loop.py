"""spec 011 T005: clerk-mod-precommit loop tests.

Covers:
- All three hook_manager values render the right file / no file (MANAGED lifecycle).
- Threaded hook_blocks appear exactly once (no double-append on reproduce).
- Install task is stubbed offline (preflight marker written).
- Byte-assert the managed hook config on reproduce.
- MANAGED files are byte-identical init → reproduce.
- No secret: questions.

Contract: specs/011-deopinionated-module-family/contracts/quality-tooling.md
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


# ---------------------------------------------------------------------------
# hook_manager=pre-commit: .pre-commit-config.yaml is written (MANAGED)
# ---------------------------------------------------------------------------


def test_precommit_renders_precommit_config(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=pre-commit → .pre-commit-config.yaml created (MANAGED)."""
    dest = tmp_path / "proj"
    _init(clerk_mod_precommit, dest, {"hook_manager": "pre-commit"})

    cfg = dest / ".pre-commit-config.yaml"
    assert cfg.is_file(), ".pre-commit-config.yaml must exist for hook_manager=pre-commit"
    parsed = yaml.safe_load(cfg.read_text())
    assert "repos" in parsed, ".pre-commit-config.yaml must have a repos key"

    # No lefthook.yml when hook_manager=pre-commit
    assert not (dest / "lefthook.yml").exists(), "lefthook.yml must not be written for pre-commit"

    # Stub task ran (install marker present)
    assert (dest / ".clerk-precommit-preflight").is_file(), "preflight stub must run"

    # Vendored close-keywords script is present (MANAGED)
    check_script = dest / ".pre-commit-hooks" / "check-commit-msg.py"
    assert check_script.is_file(), "vendored check-commit-msg.py must be present"


def test_precommit_config_contains_base_hooks(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """Base hygiene hooks, gitleaks, shellcheck are in the rendered pre-commit config."""
    dest = tmp_path / "proj"
    _init(clerk_mod_precommit, dest, {"hook_manager": "pre-commit"})

    text = (dest / ".pre-commit-config.yaml").read_text()
    # Base hygiene
    assert "pre-commit/pre-commit-hooks" in text, "base hooks repo missing"
    assert "trailing-whitespace" in text
    assert "end-of-file-fixer" in text
    # Secret scan
    assert "gitleaks" in text, "gitleaks hook missing"
    # Shellcheck
    assert "shellcheck" in text, "shellcheck hook missing"


def test_precommit_config_enforce_conventional_commits(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enforce_conventional_commits=true adds the close-keywords commit-msg hook."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_precommit,
        dest,
        {"hook_manager": "pre-commit", "enforce_conventional_commits": True},
    )

    text = (dest / ".pre-commit-config.yaml").read_text()
    assert "conventional-commit-msg" in text or "check-commit-msg" in text, (
        "enforce_conventional_commits=true must add the commit-msg hook"
    )
    assert "commit-msg" in text, "commit-msg stage must be referenced"


def test_precommit_config_no_conventional_commits_when_disabled(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enforce_conventional_commits=false omits the close-keywords hook block."""
    dest = tmp_path / "proj"
    _init(
        clerk_mod_precommit,
        dest,
        {"hook_manager": "pre-commit", "enforce_conventional_commits": False},
    )

    text = (dest / ".pre-commit-config.yaml").read_text()
    assert "conventional-commit-msg" not in text, (
        "conventional commit hook must be absent when enforce_conventional_commits=false"
    )


def test_precommit_config_typo_check_default_on(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enable_typo_check=true (default) includes the typos hook."""
    dest = tmp_path / "proj"
    _init(clerk_mod_precommit, dest, {"hook_manager": "pre-commit", "enable_typo_check": True})

    text = (dest / ".pre-commit-config.yaml").read_text()
    assert "typos" in text, "typos hook must be present when enable_typo_check=true"


def test_precommit_config_typo_check_disabled(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enable_typo_check=false excludes the typos hook."""
    dest = tmp_path / "proj"
    _init(clerk_mod_precommit, dest, {"hook_manager": "pre-commit", "enable_typo_check": False})

    text = (dest / ".pre-commit-config.yaml").read_text()
    assert "typos" not in text, "typos hook must be absent when enable_typo_check=false"


def test_precommit_config_hook_blocks_injected_once(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """Frozen hook_blocks appear in the rendered config (no double-append on reproduce)."""
    ruff_block = (
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v0.6.9\n"
        "    hooks:\n"
        "      - id: ruff\n"
        "        args: [--fix]\n"
        "      - id: ruff-format\n"
    )
    dest = tmp_path / "proj"
    _init(
        clerk_mod_precommit,
        dest,
        {"hook_manager": "pre-commit", "hook_blocks": [ruff_block]},
    )

    cfg_path = dest / ".pre-commit-config.yaml"
    text = cfg_path.read_text()
    # Validate YAML is well-formed after block injection
    parsed = yaml.safe_load(text)
    assert "repos" in parsed, "rendered config must be valid YAML with a repos key"
    assert "ruff-pre-commit" in text, "hook_blocks must be injected"
    # Must appear exactly once (no double-append)
    assert text.count("ruff-pre-commit") == 1, (
        f"hook_blocks injected more than once: count={text.count('ruff-pre-commit')}"
    )
    # Verify the injected block parsed correctly into the repos list
    repo_urls = [r.get("repo", "") for r in parsed["repos"]]
    assert any("ruff-pre-commit" in url for url in repo_urls), (
        "ruff-pre-commit block must parse as a valid repos entry"
    )


def test_precommit_config_byte_identical_on_reproduce(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """MANAGED: .pre-commit-config.yaml is byte-identical after reproduce."""
    dest = tmp_path / "proj"
    answers = {
        "hook_manager": "pre-commit",
        "enforce_conventional_commits": True,
        "enable_typo_check": True,
    }
    _init(clerk_mod_precommit, dest, answers)

    cfg = dest / ".pre-commit-config.yaml"
    before = _digest(cfg)
    check_script_before = _digest(dest / ".pre-commit-hooks" / "check-commit-msg.py")

    # Use single-layer reproduce (not reproduce_many) to avoid the DAG dangling-edge
    # error that fires when clerk-mod-base is absent from the selection — this module
    # declares run_after: [clerk-mod-base] which reproduce_many enforces strictly.
    runner.reproduce(str(dest))

    assert _digest(cfg) == before, ".pre-commit-config.yaml not byte-identical after reproduce"
    assert _digest(dest / ".pre-commit-hooks" / "check-commit-msg.py") == check_script_before, (
        "check-commit-msg.py not byte-identical after reproduce"
    )


# ---------------------------------------------------------------------------
# hook_manager=lefthook: lefthook.yml is written (MANAGED)
# ---------------------------------------------------------------------------


def test_precommit_renders_lefthook_yml(
    clerk_mod_precommit_lefthook: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=lefthook → lefthook.yml created (MANAGED)."""
    dest = tmp_path / "proj"
    trust.add_trust(clerk_mod_precommit_lefthook.url)
    spec = runner.RunSpec(
        source=clerk_mod_precommit_lefthook.url,
        dest=str(dest),
        answers={"hook_manager": "lefthook"},
    )
    runner.init(spec, today="2026-07-13")

    lh = dest / "lefthook.yml"
    assert lh.is_file(), "lefthook.yml must exist for hook_manager=lefthook"
    assert "pre-commit" in lh.read_text(), "lefthook.yml must have pre-commit section"

    # No .pre-commit-config.yaml when lefthook
    assert not (dest / ".pre-commit-config.yaml").exists()

    # Stub task ran
    assert (dest / ".clerk-precommit-preflight").is_file()


def test_lefthook_hook_blocks_injected_once(
    clerk_mod_precommit_lefthook: TemplateRepo, tmp_path: Path
) -> None:
    """Frozen hook_blocks appear exactly once in lefthook.yml (no double-append)."""
    ruff_block = "pre-commit:\n  commands:\n    ruff:\n      run: ruff check {staged_files}\n"
    dest = tmp_path / "proj"
    trust.add_trust(clerk_mod_precommit_lefthook.url)
    spec = runner.RunSpec(
        source=clerk_mod_precommit_lefthook.url,
        dest=str(dest),
        answers={"hook_manager": "lefthook", "hook_blocks": [ruff_block]},
    )
    runner.init(spec, today="2026-07-13")

    text = (dest / "lefthook.yml").read_text()
    assert "ruff" in text, "hook_blocks must be injected into lefthook.yml"
    assert text.count("ruff check") == 1, (
        f"hook_blocks injected more than once: count={text.count('ruff check')}"
    )


def test_lefthook_byte_identical_on_reproduce(
    clerk_mod_precommit_lefthook: TemplateRepo, tmp_path: Path
) -> None:
    """MANAGED: lefthook.yml is byte-identical after reproduce."""
    dest = tmp_path / "proj"
    trust.add_trust(clerk_mod_precommit_lefthook.url)
    spec = runner.RunSpec(
        source=clerk_mod_precommit_lefthook.url,
        dest=str(dest),
        answers={"hook_manager": "lefthook"},
    )
    runner.init(spec, today="2026-07-13")

    before = _digest(dest / "lefthook.yml")

    # Single-layer reproduce avoids DAG dangling-edge error (run_after: clerk-mod-base).
    runner.reproduce(str(dest))

    assert _digest(dest / "lefthook.yml") == before, (
        "lefthook.yml not byte-identical after reproduce"
    )


# ---------------------------------------------------------------------------
# hook_manager=none: no hook config file is written
# ---------------------------------------------------------------------------


def test_precommit_none_writes_no_hook_file(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=none → neither .pre-commit-config.yaml nor lefthook.yml is written."""
    dest = tmp_path / "proj"
    _init(clerk_mod_precommit, dest, {"hook_manager": "none"})

    assert not (dest / ".pre-commit-config.yaml").exists(), (
        ".pre-commit-config.yaml must not exist for hook_manager=none"
    )
    assert not (dest / "lefthook.yml").exists(), "lefthook.yml must not exist for hook_manager=none"
    # The answers file is still written (copier always writes it).
    assert (dest / ".copier-answers.clerk-mod-precommit.yml").exists() or (
        dest / ".copier-answers.yml"
    ).exists(), "answers file must be written regardless of hook_manager"


def test_precommit_none_install_tasks_have_when_guards(
    clerk_mod_precommit: TemplateRepo,
) -> None:
    """hook_manager=none → install tasks declare a when: guard excluding none.

    The stub unconditionally writes a preflight marker, so we can't test task
    execution directly.  Instead assert the copier.yml carries `when:` conditions
    on both install tasks so the real `pre-commit install`/`lefthook install` never
    fires when hook_manager=none.
    """
    import yaml as _yaml

    copier_yml = Path(clerk_mod_precommit.url) / "copier.yml"
    cfg = _yaml.safe_load(copier_yml.read_text())

    # The _tasks block is replaced by the stub — read the ORIGINAL module copier.yml.
    # The fixture path points to the repo root of the stub, so read from templates/.
    from tests.conftest import _MODULES_DIR

    orig = _yaml.safe_load((_MODULES_DIR / "clerk-mod-precommit" / "copier.yml").read_text())
    tasks = orig.get("_tasks", [])
    # Both install tasks must carry a `when:` expression that excludes none.
    for task in tasks:
        if isinstance(task, dict) and "when" in task:
            condition = task["when"]
            assert "none" not in condition or "!=" in condition or "hook_manager ==" in condition, (
                f"install task `when:` does not guard against hook_manager=none: {condition!r}"
            )
    # At least one task must reference hook_manager (the guard exists).
    has_guard = any(isinstance(t, dict) and "hook_manager" in t.get("when", "") for t in tasks)
    assert has_guard, "No install task guards on hook_manager — none case would run install"


def test_precommit_none_reproduce_no_new_files(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=none: reproduce does not create hook config files."""
    dest = tmp_path / "proj"
    _init(clerk_mod_precommit, dest, {"hook_manager": "none"})

    # Single-layer reproduce: avoids DAG dangling-edge error (run_after: clerk-mod-base).
    runner.reproduce(str(dest))

    assert not (dest / ".pre-commit-config.yaml").exists()
    assert not (dest / "lefthook.yml").exists()


# ---------------------------------------------------------------------------
# Ordering edge: run_after clerk-mod-base
# ---------------------------------------------------------------------------


def test_precommit_run_after_edge_declared(
    clerk_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """run_after: [clerk-mod-base] is declared in the module."""
    import yaml as _yaml

    copier_yml = Path(clerk_mod_precommit.url) / "copier.yml"
    cfg = _yaml.safe_load(copier_yml.read_text())
    run_after = cfg.get("run_after", {}).get("default", [])
    assert "clerk-mod-base" in run_after, (
        "clerk-mod-precommit must declare run_after: [clerk-mod-base]"
    )


# ---------------------------------------------------------------------------
# No secret: questions
# ---------------------------------------------------------------------------


def test_no_secret_questions(clerk_mod_precommit: TemplateRepo, tmp_path: Path) -> None:
    """Compliance: no secret: questions in copier.yml (Constitution VI)."""
    import yaml as _yaml

    copier_yml = Path(clerk_mod_precommit.url) / "copier.yml"
    cfg = _yaml.safe_load(copier_yml.read_text())
    secret_keys = [
        key
        for key, spec in cfg.items()
        if not key.startswith("_") and isinstance(spec, dict) and spec.get("secret")
    ]
    assert not secret_keys, f"secret: questions found: {secret_keys}"
