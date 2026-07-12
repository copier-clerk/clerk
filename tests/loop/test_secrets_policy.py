"""SC-001 / SC-002: clerk-authored templates must not declare secret questions.

Phase-1 policy lint (T001) — runs discovery over in-repo clerk-authored templates
and asserts no secret questions are declared.  A fixture template that violates
the policy fails the same check.

Phase-2 guardrail (T004) — a third-party template with a secret question is
surfaced as "do not collect"; discovery reports it in secret_questions.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from clerk import discovery
from tests.conftest import build_template_repo

# ---------------------------------------------------------------------------
# Phase 1: policy lint over in-repo clerk-authored templates (T001 / SC-001)
# ---------------------------------------------------------------------------

# Discover all clerk-authored template roots in this repo.  Any directory that
# contains a copier.yml/.yaml at its root (excluding specs/ and .specify/) is a
# candidate; we further restrict to known first-party paths.
_REPO_ROOT = Path(__file__).parent.parent.parent
_CLERK_TEMPLATE_DIRS: list[Path] = sorted(
    p.parent for p in _REPO_ROOT.glob("examples/*/copier.yml")
)


@pytest.mark.parametrize("template_dir", _CLERK_TEMPLATE_DIRS, ids=lambda p: p.name)
def test_clerk_authored_template_has_no_secret_questions(template_dir: Path) -> None:
    """A clerk-authored template must not declare any secret: true questions (FR-001 / SC-001)."""
    # discovery.discover() requires a fetchable git source; read the copier.yml
    # directly for the policy check — no network, no git clone needed.
    import yaml

    config = template_dir / "copier.yml"
    if not config.exists():
        config = template_dir / "copier.yaml"
    raw = yaml.safe_load(config.read_text()) or {}

    # Check per-question secret: true
    per_question = [
        key
        for key, spec in raw.items()
        if not key.startswith("_") and isinstance(spec, dict) and spec.get("secret", False)
    ]
    # Check top-level _secret_questions list form
    list_form = list(raw.get("_secret_questions") or [])

    violations = per_question + [k for k in list_form if k not in per_question]
    assert violations == [], (
        f"clerk-authored template {template_dir.name!r} declares secret question(s): "
        f"{violations!r}. "
        f"Secrets belong in the generated project's runtime config (.env.example + docs), "
        f"not in copier answers. See specs/005-secrets/contracts/secrets.md for the pattern."
    )


def test_fixture_with_secret_question_fails_policy(tmp_path: Path) -> None:
    """A fixture template declaring a secret: true question is caught by the policy check."""
    copier_yml = dedent(
        """\
        project_name:
          type: str
        api_token:
          type: str
          secret: true
          default: ""
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "bad-clerk-template",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )

    import yaml

    raw = yaml.safe_load((Path(repo.url) / "copier.yml").read_text()) or {}
    violations = [
        key
        for key, spec in raw.items()
        if not key.startswith("_") and isinstance(spec, dict) and spec.get("secret", False)
    ]
    assert "api_token" in violations, "policy check should have caught the secret question"


def test_clean_template_passes_policy(tmp_path: Path) -> None:
    """A template with no secret questions passes the policy check (SC-001 negative)."""
    copier_yml = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "clean-template",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )

    import yaml

    raw = yaml.safe_load((Path(repo.url) / "copier.yml").read_text()) or {}
    violations = [
        key
        for key, spec in raw.items()
        if not key.startswith("_") and isinstance(spec, dict) and spec.get("secret", False)
    ]
    assert violations == [], "clean template should have no secret questions"


# ---------------------------------------------------------------------------
# Phase 2: third-party guardrail (T004 / SC-002)
# ---------------------------------------------------------------------------


def test_third_party_secret_surfaced_in_secret_questions(tmp_path: Path) -> None:
    """discovery surfaces a third-party secret: true question in secret_questions (SC-002)."""
    copier_yml = dedent(
        """\
        project_name:
          type: str
        api_token:
          type: str
          secret: true
          default: ""
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "third-party-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    disc = discovery.discover(repo.url)
    assert "api_token" in disc.secret_questions, (
        "secret question must appear in secret_questions so the agent knows not to collect it"
    )


def test_secret_question_not_required_as_agent_answer(tmp_path: Path) -> None:
    """A secret question in discovery is never a required agent-collected answer.

    The SKILL path must not place it in the run-spec; this test confirms the
    semantic: secret_questions is the "do not collect" set, not the "collect" set.
    The mechanical enforcement (runner rejects secret keys) is tested separately.
    """
    copier_yml = dedent(
        """\
        project_name:
          type: str
        db_password:
          type: str
          secret: true
          default: ""
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "third-party-secret-2",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    disc = discovery.discover(repo.url)

    # The non-secret questions are what the agent collects; secret ones are excluded.
    agent_collected = [q.key for q in disc.questions if not q.secret]
    assert "db_password" not in agent_collected
    assert "project_name" in agent_collected


def test_list_form_secret_surfaced_in_secret_questions(tmp_path: Path) -> None:
    """_secret_questions list form is also surfaced in secret_questions (FR-003b / SC-003b)."""
    copier_yml = dedent(
        """\
        project_name:
          type: str
        api_key:
          type: str
          default: ""
        _secret_questions:
          - api_key
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        tmp_path / "third-party-list-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )
    disc = discovery.discover(repo.url)
    assert "api_key" in disc.secret_questions, (
        "_secret_questions list form must be recognised in secret_questions"
    )
    # The question itself should be flagged secret in the questions list too.
    api_key_q = next(q for q in disc.questions if q.key == "api_key")
    assert api_key_q.secret
