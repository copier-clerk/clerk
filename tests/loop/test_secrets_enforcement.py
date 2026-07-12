"""SC-003a / SC-003b / SC-003c: mechanical enforcement — runner rejects secret keys.

Bypasses the SKILL entirely; constructs run-specs that violate the guardrail and
asserts the code-level rejection (FR-003a/003b/003c / decision 4a/4b).
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from clerk import runner, trust
from clerk.errors import InvalidRunSpecError, SecretInAnswersError
from tests.conftest import TemplateRepo, build_template_repo

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _make_secret_template(tmp_path: Path, *, default: str = "") -> TemplateRepo:
    """A template with a single secret: true question."""
    copier_yml = dedent(
        f"""\
        project_name:
          type: str
        api_token:
          type: str
          secret: true
          default: "{default}"
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "tpl-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    return repo


def _make_list_secret_template(tmp_path: Path) -> TemplateRepo:
    """A template using the _secret_questions list form."""
    copier_yml = dedent(
        """\
        project_name:
          type: str
        webhook_secret:
          type: str
          default: ""
        _secret_questions:
          - webhook_secret
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "tpl-list-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    return repo


# ---------------------------------------------------------------------------
# SC-003a: run-spec supplying a secret key is REJECTED (single path)
# ---------------------------------------------------------------------------


def test_secret_key_in_run_spec_raises_single_path(tmp_path: Path) -> None:
    """runner.init rejects a run-spec with a secret key value — key named, value absent."""
    repo = _make_secret_template(tmp_path, default="placeholder")
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(tmp_path / "proj"),
        answers={"project_name": "demo", "api_token": "super-secret-value"},
    )
    with pytest.raises(SecretInAnswersError) as exc_info:
        runner.init(spec)

    err = exc_info.value
    assert "api_token" in err.keys
    # Key is named in the message
    assert "api_token" in str(err)
    # Value is NEVER in the message
    assert "super-secret-value" not in str(err)


def test_secret_key_rejection_exit_is_nonzero_single_path(tmp_path: Path) -> None:
    """SecretInAnswersError is a ClerkError subclass so the CLI maps it to exit 1."""
    from clerk.errors import ClerkError

    repo = _make_secret_template(tmp_path, default="placeholder")
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(tmp_path / "proj"),
        answers={"project_name": "demo", "api_token": "bad"},
    )
    with pytest.raises(SecretInAnswersError) as exc_info:
        runner.init(spec)
    assert isinstance(exc_info.value, ClerkError)


# ---------------------------------------------------------------------------
# SC-003a: run-spec supplying a secret key is REJECTED (multi-layer path)
# ---------------------------------------------------------------------------


def test_secret_key_in_run_spec_raises_multi_path(tmp_path: Path) -> None:
    """runner.init_many rejects a layer answer dict with a secret key."""
    from clerk.catalog import TemplateRecord

    repo = _make_secret_template(tmp_path, default="placeholder")
    record = TemplateRecord(
        full_id="test/tpl-secret",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name", "api_token"],
    )
    with pytest.raises(SecretInAnswersError) as exc_info:
        runner.init_many(
            [(record, {"project_name": "demo", "api_token": "s3cr3t"})],
            dest=str(tmp_path / "proj"),
        )
    assert "api_token" in exc_info.value.keys
    assert "s3cr3t" not in str(exc_info.value)


def test_secret_key_in_preflight_raises_multi_path(tmp_path: Path) -> None:
    """runner.init_many with check=True also rejects a layer with a secret key."""
    from clerk.catalog import TemplateRecord

    repo = _make_secret_template(tmp_path, default="placeholder")
    record = TemplateRecord(
        full_id="test/tpl-secret",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name", "api_token"],
    )
    with pytest.raises(SecretInAnswersError):
        runner.init_many(
            [(record, {"project_name": "demo", "api_token": "s3cr3t"})],
            dest=str(tmp_path / "proj"),
            check=True,
        )


# ---------------------------------------------------------------------------
# SC-003b: _secret_questions list form is caught (both paths)
# ---------------------------------------------------------------------------


def test_list_form_secret_rejected_single_path(tmp_path: Path) -> None:
    """_secret_questions list-form secret is rejected by runner.init (FR-003b)."""
    repo = _make_list_secret_template(tmp_path)
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(tmp_path / "proj"),
        answers={"project_name": "demo", "webhook_secret": "abc123"},
    )
    with pytest.raises(SecretInAnswersError) as exc_info:
        runner.init(spec)
    assert "webhook_secret" in exc_info.value.keys


def test_list_form_secret_rejected_multi_path(tmp_path: Path) -> None:
    """_secret_questions list-form secret is rejected by runner.init_many (FR-003b)."""
    from clerk.catalog import TemplateRecord

    repo = _make_list_secret_template(tmp_path)
    record = TemplateRecord(
        full_id="test/tpl-list-secret",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name", "webhook_secret"],
    )
    with pytest.raises(SecretInAnswersError) as exc_info:
        runner.init_many(
            [(record, {"project_name": "demo", "webhook_secret": "abc123"})],
            dest=str(tmp_path / "proj"),
        )
    assert "webhook_secret" in exc_info.value.keys


# ---------------------------------------------------------------------------
# SC-003: validator-echoing-secret is scrubbed from the surfaced error (FR-004)
# ---------------------------------------------------------------------------


def test_validator_error_secret_value_redacted(tmp_path: Path) -> None:
    """A copier validator that echoes the answer has the secret value scrubbed (FR-004).

    The validator rejects the non-secret field here to trigger a ValueError from
    copier; the secret answer (passed via data=) must not appear in the raised error.
    Note: _check_no_secrets runs first, so we use a non-secret field with a validator
    and a separate secret field that has a real (non-empty) default, then verify
    the error from the validator path does not leak any data value.
    """
    # Template with a validator on project_name that always fails + a secret with default.
    # We do NOT supply the secret key in answers (would trigger SecretInAnswersError first).
    # We supply a non-secret value that will fail the validator — but the secret default
    # ("placeholder") could appear in a copier error message; we verify it's scrubbed.
    copier_yml = dedent(
        """\
        project_name:
          type: str
          validator: "{% if project_name == 'bad' %}invalid name: {{ project_name }}{% endif %}"
        api_token:
          type: str
          secret: true
          default: "placeholder-default"
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "tpl-validator",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(tmp_path / "proj"),
        answers={"project_name": "bad"},
        # Note: no api_token supplied — would be SecretInAnswersError otherwise.
    )
    # The validator fires on project_name; the error must not contain the secret default.
    with pytest.raises(Exception) as exc_info:
        runner.init(spec)
    error_msg = str(exc_info.value)
    # The secret default must not leak into the surfaced error.
    assert "placeholder-default" not in error_msg


# ---------------------------------------------------------------------------
# SC-003c: required secret with no value fails loud, not defaulted (FR-003c)
# ---------------------------------------------------------------------------


def test_required_secret_no_value_fails_loud(tmp_path: Path) -> None:
    """A required secret (empty/None default) with no value supplied → InvalidRunSpecError.

    Clerk must NOT let copier render the placeholder default silently (decision 4b /
    Constitution V).
    """
    # No default at all = required secret.
    copier_yml = dedent(
        """\
        project_name:
          type: str
        db_password:
          type: str
          secret: true
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "tpl-required-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(tmp_path / "proj"),
        answers={"project_name": "demo"},
        # db_password not supplied and has no default
    )
    with pytest.raises(InvalidRunSpecError) as exc_info:
        runner.init(spec)
    # Must name the question
    assert "db_password" in str(exc_info.value)


def test_required_secret_no_value_fails_loud_multi_path(tmp_path: Path) -> None:
    """Same fail-loud check on the init_many path (FR-003c, multi-layer)."""
    from clerk.catalog import TemplateRecord

    copier_yml = dedent(
        """\
        project_name:
          type: str
        db_password:
          type: str
          secret: true
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "tpl-required-secret-m",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    record = TemplateRecord(
        full_id="test/tpl-required-secret",
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name", "db_password"],
    )
    with pytest.raises(InvalidRunSpecError) as exc_info:
        runner.init_many(
            [(record, {"project_name": "demo"})],
            dest=str(tmp_path / "proj"),
        )
    assert "db_password" in str(exc_info.value)


def test_secret_with_nonempty_default_does_not_fail_loud(tmp_path: Path) -> None:
    """A secret with a non-empty default is NOT flagged when no value is supplied.

    clerk only fails loud when the secret has a falsy default (i.e. there is no
    real fallback). A real default like "changeme" is still a valid placeholder
    from the template's perspective — though the user should supply the real value.
    """
    # api_token has a non-empty default — should NOT trigger fail-loud.
    repo = _make_secret_template(tmp_path, default="some-placeholder")
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(tmp_path / "proj"),
        answers={"project_name": "demo"},
        # api_token not supplied, but has default="some-placeholder"
    )
    # Should NOT raise InvalidRunSpecError — the template has a usable default.
    # It may raise other errors (e.g. trust) but not the fail-loud secret check.
    # We only care that _check_required_secrets_supplied doesn't fire.
    from clerk import discovery
    from clerk.runner import _check_required_secrets_supplied

    desc = discovery.discover(repo.url, spec.ref)
    _check_required_secrets_supplied(spec.answers, desc)  # must not raise
