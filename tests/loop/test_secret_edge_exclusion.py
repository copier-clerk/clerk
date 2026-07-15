"""FR-013 / SC-012: secrets and hidden ordering values are not persisted.

Extended by spec 005 (T005 / SC-003): assert no secret value leaks to
stdout/stderr, --pretend output, or copier's argv.

Note on test design: bailiff's mechanical enforcement (FR-003a) rejects secret
keys in the run-spec before any copier call.  To verify copier's own
non-persistence guarantee (the original FR-013 intent), tests that need to pass
a secret value to copier call run_copy() directly — bypassing bailiff's guard.
This is intentional: it proves the non-persistence is a copier-level invariant,
not just a side-effect of bailiff's rejection.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml
from copier import run_copy

from bailiff import runner, trust
from tests.conftest import TemplateRepo


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def test_secret_excluded_from_recorded_answers_copier_level(
    secret_edge_template: TemplateRepo, tmp_path: Path
) -> None:
    """copier itself never persists a secret: true answer to .copier-answers.yml (FR-013).

    Calls run_copy() directly (bypassing bailiff's guardrail) to confirm the
    non-persistence is copier's own invariant, not only bailiff's rejection.
    """
    trust.add_trust(secret_edge_template.url)
    dest = tmp_path / "proj"
    dest.mkdir()
    # Call run_copy directly with a secret value to test copier's own non-persistence.
    run_copy(
        secret_edge_template.url,
        str(dest),
        data={"project_name": "demo", "api_token": "s3cr3t-should-not-persist"},
        vcs_ref=secret_edge_template.tag,
        defaults=True,
        overwrite=True,
        quiet=True,
    )

    recorded = (dest / ".copier-answers.yml").read_text()
    answers = yaml.safe_load(recorded)
    # the secret value never lands on disk — copier's own exclusion
    assert "s3cr3t-should-not-persist" not in recorded
    assert "api_token" not in answers
    # the when:false dependency edge is not persisted either
    assert "depends_on" not in answers
    # the ordinary answer is recorded
    assert answers["project_name"] == "demo"


def test_bailiff_init_rejects_secret_key_in_answers(
    secret_edge_template: TemplateRepo, tmp_path: Path
) -> None:
    """bailiff rejects a run-spec that supplies a secret key value (FR-003a / SC-003a).

    This is bailiff's enforcement layer on top of copier's own non-persistence.
    """
    from bailiff.errors import SecretInAnswersError

    trust.add_trust(secret_edge_template.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=secret_edge_template.url,
        dest=str(dest),
        answers={"project_name": "demo", "api_token": "s3cr3t"},
    )
    with pytest.raises(SecretInAnswersError) as exc_info:
        runner.init(spec, today="2026-07-09")
    # Key is named; value is never echoed
    assert "api_token" in str(exc_info.value)
    assert "s3cr3t" not in str(exc_info.value)


def test_edge_excluded_from_recorded_answers(
    secret_edge_template: TemplateRepo, tmp_path: Path
) -> None:
    """The when:false dependency edge is not persisted (FR-013, non-secret aspect).

    Uses a template with a non-empty secret default so fail-loud doesn't trigger
    when no secret value is supplied.
    """
    from textwrap import dedent

    from tests.conftest import build_template_repo

    # Template with a secret that has a real (non-empty) default and a when:false edge.
    copier_yml = dedent(
        """\
        project_name:
          type: str
        api_token:
          type: str
          secret: true
          default: "placeholder"
        depends_on:
          type: yaml
          default: ["bailiff-mod-base"]
          when: false
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "bailiff-mod-edge",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    dest = tmp_path / "proj"
    spec = runner.RunSpec(
        source=repo.url,
        dest=str(dest),
        answers={"project_name": "demo"},
    )
    runner.init(spec, today="2026-07-09")

    recorded = (dest / ".copier-answers.yml").read_text()
    answers = yaml.safe_load(recorded)
    # the secret key is never written to disk
    assert "api_token" not in answers
    # the when:false dependency edge is not persisted either
    assert "depends_on" not in answers
    # the ordinary answer is recorded
    assert answers["project_name"] == "demo"


def test_secret_value_absent_from_pretend_output_copier_level(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A secret value must not appear in --pretend output (SC-003).

    Uses a template with a non-empty secret default and calls run_copy(pretend=True)
    directly to verify copier's own dry-run doesn't leak the secret default value
    into captured output.
    """
    from textwrap import dedent

    from tests.conftest import build_template_repo

    copier_yml = dedent(
        """\
        project_name:
          type: str
        api_token:
          type: str
          secret: true
          default: "sentinel-secret-default"
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "tpl-pretend-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    trust.add_trust(repo.url)
    dest = tmp_path / "proj"
    dest.mkdir()
    # Call run_copy with pretend=True; the secret default must not appear in output.
    run_copy(
        repo.url,
        str(dest),
        data={"project_name": "demo"},
        vcs_ref=repo.tag,
        defaults=True,
        overwrite=True,
        quiet=True,
        pretend=True,
    )
    captured = capsys.readouterr()
    assert "sentinel-secret-default" not in captured.out
    assert "sentinel-secret-default" not in captured.err


def test_no_secret_on_argv() -> None:
    """bailiff never builds a 'copier --data key=value' argv — always uses run_copy(data=…).

    This is a structural invariant of runner.py: no subprocess call with copier args
    exists, so secret values can never leak into process listings (FR-004).
    """
    import bailiff.runner as runner_mod

    src = inspect.getsource(runner_mod)
    assert "subprocess" not in src, (
        "runner.py must not use subprocess to call copier — use run_copy(data=...) "
        "so secret values never appear in argv / process listings"
    )
