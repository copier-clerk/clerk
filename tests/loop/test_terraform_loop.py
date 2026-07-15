"""T020: bailiff-mod-terraform loop tests (spec 011 / iac.md).

Init + reproduce assertions for both tf_flavor=terraform and tf_flavor=opentofu.

Lifecycle classes asserted:
  MANAGED     — versions.tf, .tflint.hcl, .terraform-version: byte-identical on
                init AND reproduce (content matched exactly).
  SEED-ONCE   — main.tf, variables.tf, outputs.tf, backend.tf,
                terraform.tfvars.example: present after init; NOT overwritten on
                reproduce when already present (_skip_if_exists guard).
  TASK-OUTPUT — .terraform.lock.hcl: present after init (written by the stubbed
                init task); asserted for PRESENCE/STRUCTURE only (R5), never
                regenerated on a reproduce over an already-committed tree.

Tasks are stubbed via _copy_module_with_stub_tasks (_TERRAFORM_STUB_TASKS /
_TOFU_STUB_TASKS) — the real terraform/tofu init is network-gated; the stub
writes .bailiff-terraform-preflight as the marker and simulates the task-output
lock file with a deterministic placeholder so the suite stays hermetic.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import (
    TemplateRepo,
    _copy_module_with_stub_tasks,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Extended stub tasks that also produce the task-output .terraform.lock.hcl
# placeholder so the TASK-OUTPUT lifecycle assertion works without a real
# `terraform init` call. The real init writes this file; the stub mimics it.
_TF_STUB_WITH_LOCK = dedent(
    """\
    _tasks:
      - "printf 'terraform-preflight-ok\\n' > .bailiff-terraform-preflight"
      - >-
        test -f infrastructure/.terraform.lock.hcl ||
        printf '# This file is maintained automatically by "terraform init".\\n'
        > infrastructure/.terraform.lock.hcl
    """
)

_TOFU_STUB_WITH_LOCK = dedent(
    """\
    _tasks:
      - "printf 'tofu-preflight-ok\\n' > .bailiff-terraform-preflight"
      - >-
        test -f infrastructure/.terraform.lock.hcl ||
        printf '# This file is maintained automatically by "tofu init".\\n'
        > infrastructure/.terraform.lock.hcl
    """
)


@pytest.fixture
def bailiff_mod_terraform(tmp_path: Path) -> TemplateRepo:
    """bailiff-mod-terraform with terraform flavor (init task stubbed, lock stub added)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-terraform",
        tmp_path / "bailiff-mod-terraform",
        _TF_STUB_WITH_LOCK,
    )


@pytest.fixture
def bailiff_mod_terraform_tofu(tmp_path: Path) -> TemplateRepo:
    """bailiff-mod-terraform with opentofu flavor (init task stubbed, lock stub added)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-terraform",
        tmp_path / "bailiff-mod-terraform-tofu",
        _TOFU_STUB_WITH_LOCK,
    )


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init(repo: TemplateRepo, dest: Path, answers: dict) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


def _reproduce(repo: TemplateRepo, dest: Path) -> None:
    runner.reproduce(str(dest))


# ---------------------------------------------------------------------------
# terraform flavor tests
# ---------------------------------------------------------------------------


class TestTerraformFlavor:
    """Tests for tf_flavor=terraform (default)."""

    def test_init_produces_managed_files(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """MANAGED files exist after init with expected content."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {
                "tf_flavor": "terraform",
                "terraform_version": "1.12.2",
                "tflint_version": "0.57.0",
                "placement_dir": "infrastructure",
            },
        )

        # MANAGED: versions.tf contains required_version
        versions = (dest / "infrastructure" / "versions.tf").read_text()
        assert "required_version" in versions
        assert "1.12.2" in versions

        # MANAGED: .tflint.hcl has terraform plugin block
        tflint = (dest / "infrastructure" / ".tflint.hcl").read_text()
        assert 'plugin "terraform"' in tflint
        assert "recommended" in tflint

        # MANAGED: .terraform-version pins the version
        tv = (dest / "infrastructure" / ".terraform-version").read_text().strip()
        assert tv == "1.12.2"

    def test_init_produces_seed_once_files(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """SEED-ONCE files are present after init."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {
                "tf_flavor": "terraform",
                "terraform_version": "1.12.2",
                "tflint_version": "0.57.0",
            },
        )
        iac = dest / "infrastructure"
        assert (iac / "main.tf").is_file(), "main.tf missing after init"
        assert (iac / "variables.tf").is_file(), "variables.tf missing after init"
        assert (iac / "outputs.tf").is_file(), "outputs.tf missing after init"
        assert (iac / "backend.tf").is_file(), "backend.tf missing after init"
        assert (iac / "terraform.tfvars.example").is_file(), "tfvars.example missing"

    def test_backend_tf_dynamodb_comment_for_terraform_flavor(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """backend.tf contains DynamoDB comment for terraform flavor."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {"tf_flavor": "terraform", "terraform_version": "1.12.2", "tflint_version": "0.57.0"},
        )
        backend = (dest / "infrastructure" / "backend.tf").read_text()
        assert "dynamodb_table" in backend, "terraform flavor must show DynamoDB lock comment"
        assert "use_lockfile" not in backend, "terraform flavor must not show use_lockfile"

    def test_init_produces_task_output_lock(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """TASK-OUTPUT: .terraform.lock.hcl present after init (stub produced it)."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {"tf_flavor": "terraform", "terraform_version": "1.12.2", "tflint_version": "0.57.0"},
        )
        lock = dest / "infrastructure" / ".terraform.lock.hcl"
        assert lock.is_file(), ".terraform.lock.hcl missing — task-output not produced"
        # Presence/structure only (R5): it is a text file (not empty placeholder check)
        assert lock.stat().st_size > 0, ".terraform.lock.hcl must not be empty"

    def test_preflight_stub_marker(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """The (stubbed) preflight task produced its marker file."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {"tf_flavor": "terraform", "terraform_version": "1.12.2", "tflint_version": "0.57.0"},
        )
        assert (dest / ".bailiff-terraform-preflight").is_file(), "preflight marker missing"

    def test_answers_file_recorded(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """The copier answers file is written and records the right answers."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {"tf_flavor": "terraform", "terraform_version": "1.9.0", "tflint_version": "0.50.0"},
        )
        # Answers file is named after the module when used standalone
        af_path = dest / ".copier-answers.yml"
        assert af_path.is_file(), "answers file not written"
        af = yaml.safe_load(af_path.read_text())
        assert af["tf_flavor"] == "terraform"
        assert af["terraform_version"] == "1.9.0"
        # Hidden edge answers are never persisted
        assert "run_after" not in af
        assert "depends_on" not in af

    def test_managed_byte_identical_on_reproduce(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """MANAGED files are byte-identical after reproduce (no drift)."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {
                "tf_flavor": "terraform",
                "terraform_version": "1.12.2",
                "tflint_version": "0.57.0",
                "placement_dir": "infrastructure",
            },
        )
        iac = dest / "infrastructure"
        versions_before = (iac / "versions.tf").read_text()
        tflint_before = (iac / ".tflint.hcl").read_text()
        tv_before = (iac / ".terraform-version").read_text()

        _reproduce(bailiff_mod_terraform, dest)

        assert (iac / "versions.tf").read_text() == versions_before, "versions.tf drifted"
        assert (iac / ".tflint.hcl").read_text() == tflint_before, ".tflint.hcl drifted"
        assert (iac / ".terraform-version").read_text() == tv_before, ".terraform-version drifted"

    def test_seed_once_not_overwritten_on_reproduce(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """SEED-ONCE files survive reproduce when already present (skipped)."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {"tf_flavor": "terraform", "terraform_version": "1.12.2", "tflint_version": "0.57.0"},
        )
        iac = dest / "infrastructure"

        # Simulate project edits on seed-once files
        (iac / "main.tf").write_text("# project-owned main.tf\n")
        (iac / "variables.tf").write_text("# project-owned variables.tf\n")
        (iac / "backend.tf").write_text("# project-owned backend.tf\n")

        _reproduce(bailiff_mod_terraform, dest)

        # Edits must be preserved — reproduce must not clobber them
        assert (iac / "main.tf").read_text() == "# project-owned main.tf\n"
        assert (iac / "variables.tf").read_text() == "# project-owned variables.tf\n"
        assert (iac / "backend.tf").read_text() == "# project-owned backend.tf\n"

    def test_lock_file_present_on_reproduce(
        self, bailiff_mod_terraform: TemplateRepo, tmp_path: Path
    ) -> None:
        """TASK-OUTPUT: .terraform.lock.hcl is present (committed) on reproduce (R5)."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform,
            dest,
            {"tf_flavor": "terraform", "terraform_version": "1.12.2", "tflint_version": "0.57.0"},
        )
        lock_before = (dest / "infrastructure" / ".terraform.lock.hcl").read_text()

        _reproduce(bailiff_mod_terraform, dest)

        # Must still be present; the stub task guard means it is NOT regenerated
        lock_after = (dest / "infrastructure" / ".terraform.lock.hcl").read_text()
        assert lock_after == lock_before, "lock file must not be regenerated on reproduce"


# ---------------------------------------------------------------------------
# opentofu flavor tests
# ---------------------------------------------------------------------------


class TestOpenTofuFlavor:
    """Tests for tf_flavor=opentofu."""

    def test_init_produces_managed_files(
        self, bailiff_mod_terraform_tofu: TemplateRepo, tmp_path: Path
    ) -> None:
        """MANAGED files exist after opentofu flavor init with correct version."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform_tofu,
            dest,
            {
                "tf_flavor": "opentofu",
                "opentofu_version": "1.10.0",
                "tflint_version": "0.57.0",
                "placement_dir": "infrastructure",
            },
        )

        # MANAGED: versions.tf contains required_version (opentofu version)
        versions = (dest / "infrastructure" / "versions.tf").read_text()
        assert "required_version" in versions
        assert "1.10.0" in versions

        # MANAGED: .tflint.hcl is byte-identical to terraform flavor (ruleset is the same)
        tflint = (dest / "infrastructure" / ".tflint.hcl").read_text()
        assert 'plugin "terraform"' in tflint
        assert "recommended" in tflint

        # MANAGED: .terraform-version pins the opentofu version
        tv = (dest / "infrastructure" / ".terraform-version").read_text().strip()
        assert tv == "1.10.0"

    def test_backend_tf_use_lockfile_for_opentofu_flavor(
        self, bailiff_mod_terraform_tofu: TemplateRepo, tmp_path: Path
    ) -> None:
        """backend.tf contains use_lockfile=true comment for opentofu flavor."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform_tofu,
            dest,
            {
                "tf_flavor": "opentofu",
                "opentofu_version": "1.10.0",
                "tflint_version": "0.57.0",
            },
        )
        backend = (dest / "infrastructure" / "backend.tf").read_text()
        assert "use_lockfile" in backend, "opentofu flavor must show use_lockfile comment"
        assert "dynamodb_table" not in backend, "opentofu flavor must not show dynamodb_table"

    def test_tflint_hcl_byte_identical_across_flavors(
        self,
        bailiff_mod_terraform: TemplateRepo,
        bailiff_mod_terraform_tofu: TemplateRepo,
        tmp_path: Path,
    ) -> None:
        """.tflint.hcl is byte-identical regardless of tf_flavor (shared ruleset)."""
        dest_tf = tmp_path / "proj-tf"
        dest_tofu = tmp_path / "proj-tofu"

        _init(
            bailiff_mod_terraform,
            dest_tf,
            {"tf_flavor": "terraform", "terraform_version": "1.12.2", "tflint_version": "0.57.0"},
        )
        _init(
            bailiff_mod_terraform_tofu,
            dest_tofu,
            {"tf_flavor": "opentofu", "opentofu_version": "1.10.0", "tflint_version": "0.57.0"},
        )

        tf_tflint = (dest_tf / "infrastructure" / ".tflint.hcl").read_text()
        tofu_tflint = (dest_tofu / "infrastructure" / ".tflint.hcl").read_text()
        assert tf_tflint == tofu_tflint, ".tflint.hcl must be byte-identical across flavors"

    def test_seed_once_files_present(
        self, bailiff_mod_terraform_tofu: TemplateRepo, tmp_path: Path
    ) -> None:
        """SEED-ONCE files are present after opentofu init."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform_tofu,
            dest,
            {
                "tf_flavor": "opentofu",
                "opentofu_version": "1.10.0",
                "tflint_version": "0.57.0",
            },
        )
        iac = dest / "infrastructure"
        for fname in (
            "main.tf",
            "variables.tf",
            "outputs.tf",
            "backend.tf",
            "terraform.tfvars.example",
        ):
            assert (iac / fname).is_file(), f"{fname} missing after opentofu init"

    def test_task_output_lock_present(
        self, bailiff_mod_terraform_tofu: TemplateRepo, tmp_path: Path
    ) -> None:
        """TASK-OUTPUT: .terraform.lock.hcl present after opentofu init."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform_tofu,
            dest,
            {"tf_flavor": "opentofu", "opentofu_version": "1.10.0", "tflint_version": "0.57.0"},
        )
        lock = dest / "infrastructure" / ".terraform.lock.hcl"
        assert lock.is_file(), ".terraform.lock.hcl missing after opentofu init"
        assert lock.stat().st_size > 0

    def test_preflight_stub_marker(
        self, bailiff_mod_terraform_tofu: TemplateRepo, tmp_path: Path
    ) -> None:
        """The (stubbed) preflight task produced its marker for opentofu flavor."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform_tofu,
            dest,
            {"tf_flavor": "opentofu", "opentofu_version": "1.10.0", "tflint_version": "0.57.0"},
        )
        assert (dest / ".bailiff-terraform-preflight").is_file()

    def test_seed_once_not_overwritten_on_reproduce(
        self, bailiff_mod_terraform_tofu: TemplateRepo, tmp_path: Path
    ) -> None:
        """SEED-ONCE files survive reproduce in opentofu flavor."""
        dest = tmp_path / "proj"
        _init(
            bailiff_mod_terraform_tofu,
            dest,
            {"tf_flavor": "opentofu", "opentofu_version": "1.10.0", "tflint_version": "0.57.0"},
        )
        iac = dest / "infrastructure"
        (iac / "main.tf").write_text("# tofu project main.tf\n")

        _reproduce(bailiff_mod_terraform_tofu, dest)

        assert (iac / "main.tf").read_text() == "# tofu project main.tf\n"
