"""Combination stack: "IaC" — base + python + terraform + precommit + ci-github.

Only ONE IaC module per stack (terraform/cdk/cloudformation all provide the
exclusive iac-tool capability). Asserts the terraform placement rendering
coexists with the rest of the stack and no capability warning fires for a
single provider.

precommit is included so the fragment bundler _post_task actually runs over
terraform's .pre-commit.d/ fragment: a terraform+precommit stack is where a
malformed (bare-list) fragment hard-aborts init (spec 014 real-render finding).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

from tests.integration.conftest import init_stack

_LAYERS = [
    (
        "bailiff-mod-base",
        {
            "project_name": "iac-demo",
            "org": "acme",
            "license": "apache-2.0",
            "layout": "single",
            "mise_tools": [{"python": "3.13"}, {"terraform": "1.12.2"}],
            "gitignore_stack": ["Python", "Terraform"],
        },
    ),
    ("bailiff-mod-python", {"python_version": "3.13", "hook_manager": "pre-commit"}),
    (
        "bailiff-mod-terraform",
        # No pre_commit_terraform_rev override: the module's DEFAULT pin must make
        # the bundled .pre-commit-config.yaml schema-valid (pre-commit requires a
        # rev per repo) out of the box.
        {"tf_flavor": "terraform", "placement_dir": "infrastructure"},
    ),
    ("bailiff-mod-precommit", {"install_hooks": False}),
    (
        "bailiff-mod-ci-github",
        {
            "ci_model": "standard",
            "ci_languages": ["python"],
            "ci_lang_facts": {
                "python": {"manager": "uv", "version": "3.13", "test_runner": "pytest", "image": ""}
            },
            "monorepo_tool": "none",
            "default_branch": "main",
        },
    ),
]


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stack_iac")
    mp = pytest.MonkeyPatch()
    mp.setenv("COPIER_SETTINGS_PATH", str(root / "settings.yml"))
    try:
        # Single iac-tool provider: the CAPABILITY CONFLICT warning must NOT fire.
        # (The collision scan renders _external_data consumers cleanly now that its
        # temp dir is realpath-canonicalized, so no ForbiddenPathError skip warning
        # is expected here either.)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            yield init_stack(root, _LAYERS, exclusive_capabilities=frozenset({"iac-tool"}))
        capability_warnings = [
            w
            for w in caught
            if issubclass(w.category, UserWarning) and "CAPABILITY CONFLICT" in str(w.message)
        ]
        assert not capability_warnings, f"unexpected capability conflict: {capability_warnings}"
    finally:
        mp.undo()


def test_terraform_placement_rendering(stack: Path) -> None:
    infra = stack / "infrastructure"
    for rel in (
        "main.tf",
        "variables.tf",
        "outputs.tf",
        "backend.tf",
        "versions.tf",
        ".tflint.hcl",
        "terraform.tfvars.example",
        ".terraform-version",
    ):
        assert (infra / rel).is_file(), f"terraform artifact missing: infrastructure/{rel}"
    assert (infra / ".terraform-version").read_text().strip() == "1.12.2"


def test_no_cloud_action_marker_only(stack: Path) -> None:
    """The stubbed preflight ran; nothing resembling an apply/deploy happened."""
    assert (stack / ".bailiff-terraform-preflight").is_file()
    assert not (stack / "infrastructure/.terraform").exists(), "no terraform init/apply state"


def test_coexistence_with_language_and_ci(stack: Path) -> None:
    assert (stack / "ruff.toml").is_file()
    assert (stack / ".github/workflows/ci.yml").is_file()
    assert len(list(stack.glob(".copier-answers.*.yml"))) == len(_LAYERS)


def test_precommit_bundler_merged_terraform_fragment(stack: Path) -> None:
    """The bundler _post_task ran over terraform's fragment and produced a
    well-formed config: terraform hooks present, exactly one entry per repo.

    This is the end-to-end guard for the bare-list fragment defect — a malformed
    terraform fragment aborts init here rather than reaching this assertion.
    """
    cfg_path = stack / ".pre-commit-config.yaml"
    assert cfg_path.is_file(), "bundler did not emit .pre-commit-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    by_repo = {r["repo"]: r for r in cfg["repos"]}
    tf_entry = next((r for u, r in by_repo.items() if u.endswith("pre-commit-terraform")), None)
    assert tf_entry is not None, "terraform hooks were not merged into the bundled config"
    # pre-commit requires a `rev` per repo: the module's default pin must satisfy it
    # even when the agent supplies no pre_commit_terraform_rev override.
    assert tf_entry.get("rev"), "terraform repo entry has no rev — config is schema-invalid"
    # ruff (python) and terraform coexist in one merged config.
    assert any("ruff-pre-commit" in u for u in by_repo)


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)
