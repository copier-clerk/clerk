"""spec 011 T021: clerk-mod-cdk loop test.

Init and reproduce cycles for the CDK overlay. cdk init is stubbed offline via the
_CDK_STUB_TASKS fixture so the suite stays hermetic (Constitution VII / SC-007).

Assertions per lifecycle class:
- TASK-OUTPUT (cdk init files): presence/structure only — never regenerated on
  reproduce because the `test -f <placement_dir>/cdk.json` guard makes it a no-op
  (cross-cutting §3 / critique R5). Asserted via the offline stub marker.
- cdk.context.json: committed (not gitignored); present after init.
- NEVER bootstrap/deploy: the stub replaces the entire task chain; the test
  explicitly verifies no bootstrap/deploy invocation in the copier.yml.

Loop test scenario: cdk_language=python, placement_dir=infrastructure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from clerk import runner, trust
from tests.conftest import _MODULES_DIR, TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _init_cdk(
    cdk: TemplateRepo,
    dest: Path,
    *,
    cdk_language: str = "python",
    placement_dir: str = "infrastructure",
    include_cdk_nag: bool = False,
    include_synth_validate: bool = False,
) -> None:
    trust.add_trust(cdk.url)
    spec = runner.RunSpec(
        source=cdk.url,
        dest=str(dest),
        answers={
            "project_name": "mycdkapp",
            "cdk_language": cdk_language,
            "placement_dir": placement_dir,
            "cdk_version": "2.261.0",
            "include_cdk_nag": include_cdk_nag,
            "include_synth_validate": include_synth_validate,
        },
    )
    runner.init(spec, today="2026-07-14")


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


def test_cdk_init_produces_preflight_marker(clerk_mod_cdk: TemplateRepo, tmp_path: Path) -> None:
    """Stub task runs on init and writes the offline marker (task-output presence)."""
    dest = tmp_path / "proj"
    _init_cdk(clerk_mod_cdk, dest)

    # The CDK stub writes .clerk-cdk-preflight as a task-output marker.
    assert (dest / ".clerk-cdk-preflight").is_file(), (
        "cdk preflight stub marker must be present after init"
    )


def test_cdk_answers_file_written(clerk_mod_cdk: TemplateRepo, tmp_path: Path) -> None:
    """copier writes the answers file so the layer is reproducible (FR-016).

    Standalone init writes .copier-answers.yml (default copier name); the
    layer-specific .copier-answers.clerk-mod-cdk.yml is written by init_many
    when combined with other layers. Both are valid; we check the default here.
    """
    dest = tmp_path / "proj"
    _init_cdk(clerk_mod_cdk, dest)

    # Single-template init → copier default answers file name.
    af = dest / ".copier-answers.yml"
    assert af.is_file(), "answers file must be written on init"
    data = yaml.safe_load(af.read_text())
    assert data.get("cdk_language") == "python"
    assert data.get("placement_dir") == "infrastructure"
    assert data.get("cdk_version") == "2.261.0"


def test_cdk_reproduce_is_no_op(clerk_mod_cdk: TemplateRepo, tmp_path: Path) -> None:
    """Reproduce with stub tasks is a no-op: answers file unchanged (T026 analogue)."""
    dest = tmp_path / "proj"
    _init_cdk(clerk_mod_cdk, dest)

    # Single-template init → default answers file name.
    af = dest / ".copier-answers.yml"
    before = af.read_bytes()

    # Reproduce replays the stub — guard logic in the real tasks makes reproduce
    # idempotent; the stub just overwrites the marker (same content).
    runner.reproduce(str(dest))

    after = af.read_bytes()
    assert before == after, "answers file must be byte-identical after reproduce"


def test_cdk_context_json_not_gitignored(tmp_path: Path) -> None:
    """cdk.context.json must not appear in any gitignore rendered by this module.

    The contract states it is COMMITTED (not gitignored); cdk.out/ IS gitignored.
    This test inspects the real authored copier.yml and template/ for any
    pattern that would inadvertently gitignore cdk.context.json.
    """
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    copier_yml = (module_dir / "copier.yml").read_text()

    # No gitignore template should mention cdk.context.json.
    for p in (module_dir / "template").rglob("*.jinja"):
        content = p.read_text()
        assert "cdk.context.json" not in content or "!cdk.context.json" in content, (
            f"{p}: must not gitignore cdk.context.json (it should be committed)"
        )

    # The copier.yml itself should not gitignore cdk.context.json.
    assert "cdk.context.json" not in copier_yml or "cdk.context.json COMMITTED" in copier_yml


def test_cdk_no_bootstrap_or_deploy_in_tasks() -> None:
    """NEVER cdk bootstrap/deploy — assert neither command appears in authored tasks.

    The contract (cross-cutting §3) explicitly forbids irreversible actions at scaffold.
    Loop tests cannot stub what is not there; we inspect the real copier.yml directly.
    """
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    copier_yml_text = (module_dir / "copier.yml").read_text()

    # Parse just the _tasks block to avoid false positives in comments.
    data = yaml.safe_load(copier_yml_text) or {}
    tasks = data.get("_tasks", [])

    for task in tasks:
        # Each task is either a str or a dict with a 'command' key.
        cmd = (
            task
            if isinstance(task, str)
            else (task.get("command", "") if isinstance(task, dict) else "")
        )
        assert "cdk bootstrap" not in cmd, f"NEVER cdk bootstrap in tasks: {cmd!r}"
        assert "cdk deploy" not in cmd, f"NEVER cdk deploy in tasks: {cmd!r}"


def test_cdk_no_secret_questions() -> None:
    """No secret: questions may appear in copier.yml (Constitution VI / C-07)."""
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    copier_yml_text = (module_dir / "copier.yml").read_text()

    # A YAML-level check: no question block should have secret: true/yes.
    data = yaml.safe_load(copier_yml_text) or {}
    for key, spec in data.items():
        if key.startswith("_"):
            continue
        if isinstance(spec, dict):
            assert not spec.get("secret"), f"question '{key}' must not be secret: (Constitution VI)"


def test_cdk_language_choices_present() -> None:
    """cdk_language offers the full contract-mandated choice set."""
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    data = yaml.safe_load((module_dir / "copier.yml").read_text()) or {}
    choices = data.get("cdk_language", {}).get("choices", [])
    expected = {"typescript", "python", "go", "java", "csharp"}
    assert set(choices) == expected, f"cdk_language choices must be {expected}, got {set(choices)}"
    assert data["cdk_language"]["default"] == "typescript"


def test_cdk_reproduce_task_output_present(clerk_mod_cdk: TemplateRepo, tmp_path: Path) -> None:
    """Task-output (stub marker) is present after reproduce (presence, not regeneration)."""
    dest = tmp_path / "proj"
    _init_cdk(clerk_mod_cdk, dest)

    marker = dest / ".clerk-cdk-preflight"
    assert marker.is_file()

    # Reproduce must not remove or break the marker.
    runner.reproduce(str(dest))
    assert marker.is_file(), "task-output marker must still be present after reproduce"


def test_cdk_subdirectory_is_template() -> None:
    """_subdirectory must be 'template' per contract FR-016."""
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    data = yaml.safe_load((module_dir / "copier.yml").read_text()) or {}
    assert data.get("_subdirectory") == "template", "_subdirectory must be 'template' (FR-016)"


def test_cdk_version_consumed_in_tasks() -> None:
    """cdk_version must appear in at least one _tasks entry (contract iac.md §clerk-mod-cdk).

    The contract requires 'pin cdk_version' after cdk init; if the question is
    collected but never used in tasks the pin step is missing.
    """
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    data = yaml.safe_load((module_dir / "copier.yml").read_text()) or {}
    tasks = data.get("_tasks", [])

    cmds = []
    for task in tasks:
        if isinstance(task, str):
            cmds.append(task)
        elif isinstance(task, dict):
            cmds.append(task.get("command", ""))

    joined = "\n".join(cmds)
    assert "cdk_version" in joined, (
        "cdk_version must be consumed in a _tasks entry to pin the version after cdk init "
        "(contract iac.md §clerk-mod-cdk)"
    )


def test_cdk_nag_task_uses_when_include_cdk_nag() -> None:
    """include_cdk_nag must gate at least one task via when: (contract iac.md §clerk-mod-cdk).

    The contract requires 'cdk-nag import spliced when include_cdk_nag'; the question
    is useless if no task is conditioned on it.
    """
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    data = yaml.safe_load((module_dir / "copier.yml").read_text()) or {}
    tasks = data.get("_tasks", [])

    nag_tasks = [t for t in tasks if isinstance(t, dict) and "include_cdk_nag" in t.get("when", "")]
    assert nag_tasks, (
        "At least one task must have when: ... include_cdk_nag ... to splice the cdk-nag import "
        "(contract iac.md §clerk-mod-cdk)"
    )


def test_cdk_preflight_has_language_runtime_checks() -> None:
    """Preflight must contain language-runtime-conditional tasks for non-TS languages.

    Contract (iac.md §clerk-mod-cdk) specifies 'language runtime conditional on
    cdk_language' in preflight. At minimum python/go/java/csharp each need a
    when-gated command-v check.
    """
    module_dir = _MODULES_DIR / "clerk-mod-cdk"
    data = yaml.safe_load((module_dir / "copier.yml").read_text()) or {}
    tasks = data.get("_tasks", [])

    conditional_tasks = [t for t in tasks if isinstance(t, dict) and "when" in t]
    when_bodies = "\n".join(t.get("when", "") for t in conditional_tasks)

    assert "cdk_language" in when_bodies, (
        "Preflight must include tasks conditioned on cdk_language for runtime checks "
        "(contract iac.md §clerk-mod-cdk)"
    )
    # Each non-TS language must have at least a command-v check.
    lang_binaries = [("python", "python3"), ("go", "go"), ("java", "java"), ("csharp", "dotnet")]
    for lang, binary in lang_binaries:
        lang_tasks = [
            t
            for t in conditional_tasks
            if lang in t.get("when", "") and binary in t.get("command", "")
        ]
        assert lang_tasks, (
            f"Missing language runtime preflight for cdk_language={lang!r}: "
            f"expected a when-gated 'command -v {binary}' task"
        )
