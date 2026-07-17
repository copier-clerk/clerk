"""spec 011 T005 / spec 014 Surface 2: bailiff-mod-precommit loop tests.

Covers:
- hook_manager choices: {pre-commit, none} — lefthook removed (deferred to spec 015).
- Fragment content: base hygiene hooks, gitleaks, shellcheck, typo check, conventional
  commits (conditional on answers).
- spec 014 fragment/merge model: precommit writes .pre-commit.d/bailiff-mod-precommit.yaml
  (not .pre-commit-config.yaml directly — the bundler post-task does that).
- No lefthook.yml is ever produced by this module.
- Dependency edge: depends_on: [bailiff-mod-base] (spec 014 R7 migration from run_after).
- Install task is stubbed offline (preflight marker written).
- No secret: questions.
- hook_blocks union REMOVED (spec 014 R1: fragment/merge model replaces unions).

Contract: specs/014-namespaced-question-keys/contracts/_fragment-merge.md (Surface 2)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


# ---------------------------------------------------------------------------
# hook_manager=pre-commit: fragment is written (MANAGED); bundler writes merged config
# ---------------------------------------------------------------------------


def test_precommit_writes_fragment_for_precommit(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=pre-commit → .pre-commit.d/bailiff-mod-precommit.yaml written (MANAGED).

    spec 014 Surface 2: the module writes its own fragment; the bundler (_post_task)
    assembles .pre-commit-config.yaml after the full render loop.  Single-layer init
    (runner.init) does not run _post_tasks, so only the fragment exists here.
    """
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "pre-commit"})

    fragment = dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml"
    assert fragment.is_file(), ".pre-commit.d/bailiff-mod-precommit.yaml must exist"
    parsed = yaml.safe_load(fragment.read_text())
    assert "repos" in parsed, "fragment must have a repos key"

    # Stub task ran (preflight marker present)
    assert (dest / ".bailiff-precommit-preflight").is_file(), "preflight stub must run"

    # Vendored close-keywords script is present (MANAGED)
    check_script = dest / ".pre-commit-hooks" / "check-commit-msg.py"
    assert check_script.is_file(), "vendored check-commit-msg.py must be present"

    # No lefthook.yml when hook_manager=pre-commit
    assert not (dest / "lefthook.yml").exists()


def test_precommit_fragment_contains_base_hooks(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """Base hygiene hooks, gitleaks, shellcheck are in the fragment."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "pre-commit"})

    text = (dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml").read_text()
    assert "pre-commit/pre-commit-hooks" in text, "base hooks repo missing"
    assert "trailing-whitespace" in text
    assert "end-of-file-fixer" in text
    assert "gitleaks" in text, "gitleaks hook missing"
    assert "shellcheck" in text, "shellcheck hook missing"


def test_precommit_fragment_enforce_conventional_commits(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enforce_conventional_commits=true adds the close-keywords commit-msg hook to fragment."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_precommit,
        dest,
        {"hook_manager": "pre-commit", "enforce_conventional_commits": True},
    )

    text = (dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml").read_text()
    assert "conventional-commit-msg" in text or "check-commit-msg" in text, (
        "enforce_conventional_commits=true must add the commit-msg hook to fragment"
    )
    assert "commit-msg" in text, "commit-msg stage must be referenced"


def test_precommit_fragment_no_conventional_commits_when_disabled(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enforce_conventional_commits=false omits the close-keywords hook from fragment."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_precommit,
        dest,
        {"hook_manager": "pre-commit", "enforce_conventional_commits": False},
    )

    text = (dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml").read_text()
    assert "conventional-commit-msg" not in text, (
        "conventional commit hook must be absent when enforce_conventional_commits=false"
    )


def test_precommit_fragment_typo_check_default_on(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enable_typo_check=true (default) includes the typos hook in fragment."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "pre-commit", "enable_typo_check": True})

    text = (dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml").read_text()
    assert "typos" in text, "typos hook must be present when enable_typo_check=true"


def test_precommit_fragment_typo_check_disabled(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """enable_typo_check=false excludes the typos hook from fragment."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "pre-commit", "enable_typo_check": False})

    text = (dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml").read_text()
    assert "typos" not in text, "typos hook must be absent when enable_typo_check=false"


def test_precommit_no_direct_config_file_from_single_layer_init(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """Single-layer init does not produce .pre-commit-config.yaml directly.

    The merged config is produced by the bundler _post_task, which only runs
    via init_many/reproduce_many (not single-layer runner.init).
    """
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "pre-commit"})

    # Fragment exists; merged config does NOT (post_task not run in single-layer init)
    assert (dest / ".pre-commit.d" / "bailiff-mod-precommit.yaml").is_file()
    assert not (dest / ".pre-commit-config.yaml").exists(), (
        ".pre-commit-config.yaml must not exist from single-layer init "
        "(bundler runs as _post_task in init_many only)"
    )


def test_precommit_no_hook_blocks_question(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_blocks is NOT a question in copier.yml (spec 014 R1: unions removed).

    The fragment/merge model replaces the frozen-union hook_blocks mechanism.
    """
    import yaml as _yaml

    from tests.conftest import _MODULES_DIR

    orig = _yaml.safe_load((_MODULES_DIR / "bailiff-mod-precommit" / "copier.yml").read_text())
    assert "hook_blocks" not in orig, (
        "hook_blocks must be removed from copier.yml (spec 014 fragment/merge model)"
    )


# ---------------------------------------------------------------------------
# hook_manager choices: {pre-commit, none} — lefthook absent (spec 014 / R13)
# ---------------------------------------------------------------------------


def test_hook_manager_choices_are_precommit_and_none(
    bailiff_mod_precommit: TemplateRepo,
) -> None:
    """hook_manager choices must be exactly {pre-commit, none}; lefthook is removed.

    Lefthook support is deferred to bailiff-mod-lefthook (spec 015).
    """
    import yaml as _yaml

    from tests.conftest import _MODULES_DIR

    orig = _yaml.safe_load((_MODULES_DIR / "bailiff-mod-precommit" / "copier.yml").read_text())
    choices = orig["hook_manager"]["choices"]
    assert set(choices) == {"pre-commit", "none"}, (
        f"hook_manager choices must be {{pre-commit, none}}, got {choices!r}"
    )
    assert "lefthook" not in choices, "lefthook must not be a hook_manager choice (deferred to spec 015)"


def test_hook_manager_precommit_never_produces_lefthook_yml(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=pre-commit never produces lefthook.yml."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "pre-commit"})
    assert not (dest / "lefthook.yml").exists(), "lefthook.yml must never be produced by this module"


# ---------------------------------------------------------------------------
# hook_manager=none: no hook config file is written
# ---------------------------------------------------------------------------


def test_precommit_none_writes_no_hook_file(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=none → no fragment, no .pre-commit-config.yaml, no lefthook.yml."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "none"})

    assert not (dest / ".pre-commit.d").exists() or not any(
        (dest / ".pre-commit.d").glob("*.yaml")
    ), ".pre-commit.d/*.yaml must not exist for hook_manager=none"
    assert not (dest / ".pre-commit-config.yaml").exists()
    assert not (dest / "lefthook.yml").exists()
    # The answers file is still written (copier always writes it).
    assert (dest / ".copier-answers.bailiff-mod-precommit.yml").exists() or (
        dest / ".copier-answers.yml"
    ).exists(), "answers file must be written regardless of hook_manager"


def test_precommit_none_install_tasks_have_when_guards(
    bailiff_mod_precommit: TemplateRepo,
) -> None:
    """hook_manager=none → install tasks declare a when: guard excluding none."""
    import yaml as _yaml

    from tests.conftest import _MODULES_DIR

    orig = _yaml.safe_load((_MODULES_DIR / "bailiff-mod-precommit" / "copier.yml").read_text())
    tasks = orig.get("_tasks", [])
    for task in tasks:
        if isinstance(task, dict) and "when" in task:
            condition = task["when"]
            assert "none" not in condition or "!=" in condition or "hook_manager ==" in condition, (
                f"install task `when:` does not guard against hook_manager=none: {condition!r}"
            )
    has_guard = any(isinstance(t, dict) and "hook_manager" in t.get("when", "") for t in tasks)
    assert has_guard, "No install task guards on hook_manager — none case would run install"


def test_precommit_none_reproduce_no_new_files(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """hook_manager=none: reproduce does not create hook config files."""
    dest = tmp_path / "proj"
    _init(bailiff_mod_precommit, dest, {"hook_manager": "none"})

    # Single-layer reproduce: avoids DAG dangling-edge error.
    runner.reproduce(str(dest))

    assert not (dest / ".pre-commit-config.yaml").exists()
    assert not (dest / "lefthook.yml").exists()


# ---------------------------------------------------------------------------
# Dependency ordering edge: depends_on: [bailiff-mod-base] (spec 014 R7)
# ---------------------------------------------------------------------------


def test_precommit_depends_on_edge_declared(
    bailiff_mod_precommit: TemplateRepo, tmp_path: Path
) -> None:
    """depends_on: [bailiff-mod-base] is declared (spec 014 R7: run_after migrated)."""
    import yaml as _yaml

    copier_yml = Path(bailiff_mod_precommit.url) / "copier.yml"
    cfg = _yaml.safe_load(copier_yml.read_text())
    depends_on = cfg.get("depends_on", {}).get("default", [])
    assert "bailiff-mod-base" in depends_on, (
        "bailiff-mod-precommit must declare depends_on: [bailiff-mod-base] (spec 014 R7)"
    )


# ---------------------------------------------------------------------------
# No secret: questions
# ---------------------------------------------------------------------------


def test_no_secret_questions(bailiff_mod_precommit: TemplateRepo, tmp_path: Path) -> None:
    """Compliance: no secret: questions in copier.yml (Constitution VI)."""
    import yaml as _yaml

    copier_yml = Path(bailiff_mod_precommit.url) / "copier.yml"
    cfg = _yaml.safe_load(copier_yml.read_text())
    secret_keys = [
        key
        for key, spec in cfg.items()
        if not key.startswith("_") and isinstance(spec, dict) and spec.get("secret")
    ]
    assert not secret_keys, f"secret: questions found: {secret_keys}"
