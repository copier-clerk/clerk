"""Combination stack: "IaC" — base + python + terraform + ci-github.

Only ONE IaC module per stack (terraform/cdk/cloudformation all provide the
exclusive iac-tool capability). Asserts the terraform placement rendering
coexists with the rest of the stack and no capability warning fires for a
single provider.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

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
    ("bailiff-mod-python", {"python_version": "3.13", "hook_manager": "none"}),
    (
        "bailiff-mod-terraform",
        {"tf_flavor": "terraform", "placement_dir": "infrastructure"},
    ),
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
        # Single iac-tool provider: the exclusive set must NOT trigger a warning.
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            yield init_stack(root, _LAYERS, exclusive_capabilities=frozenset({"iac-tool"}))
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


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)
