"""spec 011 / T022: bailiff-mod-cloudformation render + reproduce loop.

Tests cover:
- raw mode: template.yaml has no SAM Transform; .cfnlintrc.yaml is MANAGED.
- sam mode: template.yaml includes Transform: AWS::Serverless-2016-10-31.
- Per-env parameter files are present (seeded by task with test -f guard).
- template.yaml is NOT overwritten on reproduce (SEED-ONCE).
- aws_validate task is stubbed; marker written when aws_validate=true.
- No secret: questions.

All tasks are replaced by hermetic offline stubs via _copy_module_with_stub_tasks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from bailiff import runner, trust
from tests.conftest import TemplateRepo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init(
    repo: TemplateRepo,
    dest: Path,
    answers: dict[str, Any],
) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Tests: raw mode
# ---------------------------------------------------------------------------


def test_raw_template_yaml_rendered(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """Raw mode: template.yaml present with AWSTemplateFormatVersion, no SAM Transform."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {
            "mode": "raw",
            "stack_description": "My raw stack",
            "environment_names": ["dev", "staging", "prod"],
        },
    )

    template_path = dest / "infrastructure" / "template.yaml"
    assert template_path.is_file(), "template.yaml not rendered in placement_dir"

    text = template_path.read_text()
    assert "AWSTemplateFormatVersion" in text, "AWSTemplateFormatVersion missing"
    assert "My raw stack" in text, "stack_description not rendered"
    # Raw mode must NOT include the SAM transform.
    assert "AWS::Serverless" not in text, "SAM Transform must be absent in raw mode"
    assert "Transform:" not in text, "Transform key must be absent in raw mode"
    # Parameters(Environment) present.
    assert "Environment" in text
    # No hardcoded region/account/stackname.
    assert "us-east-1" not in text
    assert "123456789" not in text


def test_raw_per_env_parameter_files(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """Raw mode: one parameters/<env>.json exists for each environment_names entry."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {
            "mode": "raw",
            "environment_names": ["dev", "staging", "prod"],
        },
    )

    params_dir = dest / "infrastructure" / "parameters"
    for env in ("dev", "staging", "prod"):
        param_file = params_dir / f"{env}.json"
        assert param_file.is_file(), f"parameters/{env}.json not seeded"
        content = param_file.read_text()
        assert "ParameterKey" in content
        assert "Environment" in content
        assert env in content, f"env value '{env}' missing from {env}.json"


def test_cfnlintrc_managed_no_ignore_rules(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """.cfnlintrc.yaml rendered with empty ignore_checks when cfnlint_ignore_rules=[]."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {"mode": "raw", "cfnlint_ignore_rules": []},
    )

    cfnlintrc = dest / "infrastructure" / ".cfnlintrc.yaml"
    assert cfnlintrc.is_file(), ".cfnlintrc.yaml not rendered"
    text = cfnlintrc.read_text()
    assert "ignore_checks: []" in text


def test_cfnlintrc_managed_with_ignore_rules(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """.cfnlintrc.yaml includes each rule ID from cfnlint_ignore_rules."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {
            "mode": "raw",
            "cfnlint_ignore_rules": ["W3002", "E3001"],
        },
    )

    text = (dest / "infrastructure" / ".cfnlintrc.yaml").read_text()
    assert "W3002" in text
    assert "E3001" in text
    # Must be under ignore_checks key.
    assert "ignore_checks:" in text


# ---------------------------------------------------------------------------
# Tests: sam mode
# ---------------------------------------------------------------------------


def test_sam_mode_adds_transform(bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path) -> None:
    """SAM mode: template.yaml includes Transform: AWS::Serverless-2016-10-31."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {
            "mode": "sam",
            "stack_description": "My SAM stack",
        },
    )

    text = (dest / "infrastructure" / "template.yaml").read_text()
    assert "AWS::Serverless-2016-10-31" in text, "SAM Transform missing in sam mode"
    assert "Transform:" in text, "Transform key missing in sam mode"
    # Must still have the standard CFN header.
    assert "AWSTemplateFormatVersion" in text


# ---------------------------------------------------------------------------
# Tests: placement_dir
# ---------------------------------------------------------------------------


def test_custom_placement_dir(bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path) -> None:
    """placement_dir=. renders artifacts at project root."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {
            "mode": "raw",
            "placement_dir": ".",
            "environment_names": ["prod"],
        },
    )

    assert (dest / "template.yaml").is_file(), "template.yaml not at root with placement_dir=."
    assert (dest / "parameters" / "prod.json").is_file(), "prod.json not at root parameters/"
    assert (dest / ".cfnlintrc.yaml").is_file(), ".cfnlintrc.yaml not at root"


# (reproduce byte-identity test removed — invariant is now config-consistency, spec 014)


# ---------------------------------------------------------------------------
# Tests: SEED-ONCE preservation on reproduce
# ---------------------------------------------------------------------------


def test_template_yaml_not_overwritten_on_reproduce(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """template.yaml is SEED-ONCE: local edits survive reproduce."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {"mode": "raw"},
    )

    template_path = dest / "infrastructure" / "template.yaml"
    # Simulate a local edit.
    template_path.write_text("# local-edit\n")
    digest_before = _digest(template_path)

    runner.reproduce_many(str(dest))

    assert _digest(template_path) == digest_before, (
        "template.yaml was overwritten on reproduce (SEED-ONCE violated)"
    )


def test_parameter_files_not_overwritten_on_reproduce(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """parameters/<env>.json files are SEED-ONCE: local edits survive reproduce."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {"mode": "raw", "environment_names": ["dev"]},
    )

    dev_json = dest / "infrastructure" / "parameters" / "dev.json"
    dev_json.write_text('{"edited": true}\n')
    digest_before = _digest(dev_json)

    runner.reproduce_many(str(dest))

    assert _digest(dev_json) == digest_before, (
        "parameters/dev.json was overwritten on reproduce (SEED-ONCE violated)"
    )


# ---------------------------------------------------------------------------
# Tests: answers file
# ---------------------------------------------------------------------------


def test_answers_file_records_mode_and_envs(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """Answers file records mode and environment_names; no secret questions."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {
            "mode": "sam",
            "environment_names": ["qa", "prod"],
            "cfnlint_ignore_rules": ["W3002"],
        },
    )

    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert af["mode"] == "sam"
    assert af["environment_names"] == ["qa", "prod"]
    assert af["cfnlint_ignore_rules"] == ["W3002"]
    assert bailiff_mod_cloudformation.url in af["_src_path"]
    # Hidden edge answers must not be persisted.
    assert "run_after" not in af
    assert "depends_on" not in af
    # No secret questions exist, so no secret-typed value should appear.
    assert "secret" not in str(af).lower()


# ---------------------------------------------------------------------------
# Tests: aws_validate stub
# ---------------------------------------------------------------------------


def test_aws_validate_task_stubbed(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """aws_validate=true runs the (stubbed) task; stub writes its marker."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {"mode": "raw", "aws_validate": True},
    )

    # The stub writes .bailiff-aws-preflight (from _AWS_STUB_TASKS).
    assert (dest / ".bailiff-aws-preflight").is_file(), (
        "aws stub task marker not present (aws_validate=true should trigger stub)"
    )


def test_aws_validate_false_no_task(
    bailiff_mod_cloudformation: TemplateRepo, tmp_path: Path
) -> None:
    """aws_validate=false (default): the aws task does not run."""
    dest = tmp_path / "proj"
    _init(
        bailiff_mod_cloudformation,
        dest,
        {"mode": "raw", "aws_validate": False},
    )
    # With aws_validate=false, the stub task is guarded by `when: aws_validate`,
    # so it does NOT run and no marker is written.
    assert not (dest / ".bailiff-aws-preflight").is_file(), (
        "aws stub task ran despite aws_validate=false"
    )
