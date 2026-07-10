"""Hermetic test fixtures for clerk.

Every fixture builds a throwaway **local git template repo** in a tmp dir — a
faithful stand-in for a remote source that keeps the suite offline (SC-007).
copier's `git ls-remote` / clone work against local paths, so
`run_copy`/`run_recopy` and tag resolution behave exactly as they would against a
real remote, with no network.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003  (used at runtime, not only in annotations)
from textwrap import dedent

import pytest

# Preserve PATH so git resolves in the fixture's scrubbed environment, while
# GIT_CONFIG_GLOBAL/SYSTEM=/dev/null keep commits independent of the developer's
# git config (deterministic fixtures).
_PATH = os.environ.get("PATH", "/usr/bin:/bin")

# The literal answers-file template name copier requires a template to ship so
# that `.copier-answers.yml` is written (Constitution VI / FR-016). The double
# braces are intentional: the filename itself contains a Jinja expression.
ANSWERS_FILE_TEMPLATE_NAME = "{{ _copier_conf.answers_file }}.jinja"
ANSWERS_FILE_TEMPLATE_BODY = (
    "# Managed by copier — do not edit by hand.\n{{ _copier_answers|to_nice_yaml }}\n"
)


@dataclass(frozen=True)
class TemplateRepo:
    """A local template git repo built for a test."""

    path: Path
    tag: str

    @property
    def url(self) -> str:
        """The fetchable source locator (a local path acts like a remote here)."""
        return str(self.path)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        # Deterministic, identity-independent commits so fixtures never depend on
        # the developer's global git config.
        env={
            "GIT_AUTHOR_NAME": "clerk-test",
            "GIT_AUTHOR_EMAIL": "test@clerk.invalid",
            "GIT_COMMITTER_NAME": "clerk-test",
            "GIT_COMMITTER_EMAIL": "test@clerk.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": _PATH,
        },
    )


def build_template_repo(
    root: Path,
    *,
    files: dict[str, str],
    tag: str = "v1.0.0",
    ship_answers_file: bool = True,
) -> TemplateRepo:
    """Write `files` under `root`, init a git repo, and tag it.

    `files` keys are POSIX-relative paths under the repo root. When
    `ship_answers_file` is true the required
    `template/{{ _copier_conf.answers_file }}.jinja` is added automatically unless
    already present in `files`.
    """
    root.mkdir(parents=True, exist_ok=True)
    all_files = dict(files)
    answers_rel = f"template/{ANSWERS_FILE_TEMPLATE_NAME}"
    if ship_answers_file and answers_rel not in all_files:
        all_files[answers_rel] = ANSWERS_FILE_TEMPLATE_BODY

    for rel, body in all_files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)

    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "template")
    _git(root, "tag", tag)
    return TemplateRepo(path=root, tag=tag)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

_BASE_COPIER_YML = dedent(
    """\
    project_name:
      type: str
    org:
      type: str
      default: acme
    license:
      type: str
      choices: ["MIT", "Apache-2.0"]
      default: Apache-2.0
    description:
      type: str
      default: ""
    today:
      type: str
      default: ""

    _subdirectory: template
    _tasks:
      # Hermetic and commit-free (FR-018): initializing an already-initialized
      # repo is a no-op, so this is safe to re-run at reproduce and seeds no
      # time-varying bytes.
      - "git init --quiet"
    """
)

_BASE_OUT = "name={{ project_name }} org={{ org }} license={{ license }} date={{ today }}\n"


@pytest.fixture
def base_template(tmp_path: Path) -> TemplateRepo:
    """The exemplar-shaped template: identity questions + a hermetic git-init task.

    Stands in for `clerk-mod-base` in hermetic tests.
    """
    return build_template_repo(
        tmp_path / "clerk-mod-base",
        files={
            "copier.yml": _BASE_COPIER_YML,
            "template/README.md.jinja": "# {{ project_name }}\n\n{{ description }}\n",
            "template/out.txt.jinja": _BASE_OUT,
        },
    )


@pytest.fixture
def secret_edge_template(tmp_path: Path) -> TemplateRepo:
    """A template carrying one secret question and one when:false dependency edge.

    Used to prove FR-013: secrets and hidden ordering values are NOT persisted to
    the recorded answers.
    """
    copier_yml = dedent(
        """\
        project_name:
          type: str
        api_token:
          type: str
          secret: true
          default: ""
        depends_on:
          type: yaml
          default: ["clerk-mod-base"]
          when: false

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "clerk-mod-secret",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
    )


@pytest.fixture
def no_answers_file_template(tmp_path: Path) -> TemplateRepo:
    """A template that omits the answers-file template → not reproducible (US5)."""
    copier_yml = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "clerk-mod-broken",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
        ship_answers_file=False,
    )
