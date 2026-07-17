"""Hermetic test fixtures for bailiff.

Every fixture builds a throwaway **local git template repo** in a tmp dir — a
faithful stand-in for a remote source that keeps the suite offline (SC-007).
copier's `git ls-remote` / clone work against local paths, so
`run_copy`/`run_recopy` and tag resolution behave exactly as they would against a
real remote, with no network.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
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
            "GIT_AUTHOR_NAME": "bailiff-test",
            "GIT_AUTHOR_EMAIL": "test@bailiff.invalid",
            "GIT_COMMITTER_NAME": "bailiff-test",
            "GIT_COMMITTER_EMAIL": "test@bailiff.invalid",
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

    Stands in for `bailiff-template-example` in hermetic tests.
    """
    return build_template_repo(
        tmp_path / "bailiff-mod-base",
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
          default: ["bailiff-mod-base"]
          when: false

        _subdirectory: template
        """
    )
    return build_template_repo(
        tmp_path / "bailiff-mod-secret",
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
        tmp_path / "bailiff-mod-broken",
        files={
            "copier.yml": copier_yml,
            "template/out.txt.jinja": "name={{ project_name }}\n",
        },
        ship_answers_file=False,
    )


# --------------------------------------------------------------------------- #
# T003: multi-source catalog fixture                                           #
# --------------------------------------------------------------------------- #

_SIMPLE_COPIER_YML = dedent(
    """\
    project_name:
      type: str
    _subdirectory: template
    """
)


@dataclass(frozen=True)
class MultiSourceCatalog:
    """Holds the catalog path and the three template repos it references.

    - ``usable_1``: tpl-alpha, reproducible, v1.0.0 — full_id "mycat/tpl-alpha"
    - ``usable_2``: tpl-beta,  reproducible, v1.1.0 — full_id "mycat/tpl-beta"
    - ``unusable``: tpl-broken, reproducible=False (no answers-file) — listed under unusable

    All sources live under the single "mycat" pointer so both namespace variants
    (basename-default) are exercised.  The catalog path is written under ``root``.
    """

    catalog_path: Path
    usable_1: TemplateRepo
    usable_2: TemplateRepo
    unusable: TemplateRepo
    pointer_name: str = field(default="mycat")


@pytest.fixture
def multi_source_catalog(tmp_path: Path) -> MultiSourceCatalog:
    """A catalog.toml naming two usable local template repos and one unusable.

    Reuses ``build_template_repo`` for all three repos.  Hermetic: all paths are
    under ``tmp_path``, no network access.  (T003)
    """
    usable_1 = build_template_repo(
        tmp_path / "tpl-alpha",
        files={
            "copier.yml": _SIMPLE_COPIER_YML,
            "template/out.txt.jinja": "hello={{ project_name }}\n",
        },
        tag="v1.0.0",
    )
    usable_2 = build_template_repo(
        tmp_path / "tpl-beta",
        files={
            "copier.yml": _SIMPLE_COPIER_YML,
            "template/out.txt.jinja": "hello={{ project_name }}\n",
        },
        tag="v1.1.0",
    )
    # Unusable: no answers-file template → reproducible=False → goes to unusable list.
    unusable = build_template_repo(
        tmp_path / "tpl-broken",
        files={
            "copier.yml": _SIMPLE_COPIER_YML,
            "template/out.txt.jinja": "hello={{ project_name }}\n",
        },
        tag="v1.0.0",
        ship_answers_file=False,
    )

    import tomli_w

    cat_path = tmp_path / "catalog.toml"
    data = {
        "catalog": [
            {
                "name": "mycat",
                "sources": [usable_1.url, usable_2.url, unusable.url],
            }
        ]
    }
    cat_path.write_bytes(tomli_w.dumps(data).encode())

    return MultiSourceCatalog(
        catalog_path=cat_path,
        usable_1=usable_1,
        usable_2=usable_2,
        unusable=unusable,
    )


# --------------------------------------------------------------------------- #
# T002: multi-template fixtures for spec 003                                  #
# --------------------------------------------------------------------------- #


# copier.yml for a template that writes to a specific output file and has a
# required question.  Each multi-template fixture uses a named subdirectory so
# copier resolves the answers-file to `.copier-answers.<basename>.yml`.
def _make_single_layer_yml(required_question: str = "project_name") -> str:
    return dedent(
        f"""\
        {required_question}:
          type: str
        _subdirectory: template
        """
    )


def _make_dependent_layer_yml(
    depends_on_basename: str, required_question: str = "project_name"
) -> str:
    """copier.yml for a template that declares ``depends_on`` pointing to another layer."""
    return dedent(
        f"""\
        {required_question}:
          type: str
        depends_on:
          type: yaml
          default: ["{depends_on_basename}"]
          when: false
        _subdirectory: template
        """
    )


@dataclass(frozen=True)
class MultiTemplateSet:
    """Handles for the five multi-template fixture groups (spec 003 / T002).

    All repos are local-git and therefore hermetic (offline).
    """

    # (a) A — no edges, writes template/a_out.txt
    tpl_a: TemplateRepo
    # (b) B — depends_on A, writes template/b_out.txt
    tpl_b: TemplateRepo
    # (c) C — no edges, writes template/c_out.txt (disjoint from D)
    tpl_c: TemplateRepo
    # (c) D — no edges, writes template/d_out.txt (disjoint from C)
    tpl_d: TemplateRepo
    # (d) E — depends_on F (part of a cycle with F)
    tpl_e: TemplateRepo
    # (d) F — depends_on E (part of a cycle with E)
    tpl_f: TemplateRepo
    # (e) collision_1 and collision_2 share basename "mymod" under different parents
    collision_1: TemplateRepo
    collision_2: TemplateRepo


def _make_record(full_id: str, repo: TemplateRepo):  # returns TemplateRecord (imported lazily)
    """Build a minimal TemplateRecord from a local fixture repo.

    Imported lazily to avoid the circular-at-module-load issue (catalog imports
    discovery which is fine, but this helper is only needed at runtime).
    """
    from bailiff.catalog import TemplateRecord

    return TemplateRecord(
        full_id=full_id,
        source=repo.url,
        ref=repo.tag,
        versions=[repo.tag],
        reproducible=True,
        has_tasks=False,
        questions=["project_name"],
    )


@pytest.fixture
def multi_template_set(tmp_path: Path) -> MultiTemplateSet:
    """Build all multi-template fixture repos for spec 003 tests.

    Returns a :class:`MultiTemplateSet` with all repos under ``tmp_path``.
    """
    tpl_a = build_template_repo(
        tmp_path / "tpl-a",
        files={
            "copier.yml": _make_single_layer_yml("project_name"),
            "template/a_out.txt.jinja": "a={{ project_name }}\n",
        },
    )
    tpl_b = build_template_repo(
        tmp_path / "tpl-b",
        files={
            "copier.yml": _make_dependent_layer_yml("tpl-a", "project_name"),
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
    )
    tpl_c = build_template_repo(
        tmp_path / "tpl-c",
        files={
            "copier.yml": _make_single_layer_yml("project_name"),
            "template/c_out.txt.jinja": "c={{ project_name }}\n",
        },
    )
    tpl_d = build_template_repo(
        tmp_path / "tpl-d",
        files={
            "copier.yml": _make_single_layer_yml("project_name"),
            "template/d_out.txt.jinja": "d={{ project_name }}\n",
        },
    )
    # Cycle pair: E depends_on F, F depends_on E.
    tpl_e = build_template_repo(
        tmp_path / "tpl-e",
        files={
            "copier.yml": _make_dependent_layer_yml("tpl-f", "project_name"),
            "template/e_out.txt.jinja": "e={{ project_name }}\n",
        },
    )
    tpl_f = build_template_repo(
        tmp_path / "tpl-f",
        files={
            "copier.yml": _make_dependent_layer_yml("tpl-e", "project_name"),
            "template/f_out.txt.jinja": "f={{ project_name }}\n",
        },
    )
    # Basename-collision pair: two repos named "mymod" under different parent dirs.
    collision_1 = build_template_repo(
        tmp_path / "org1" / "mymod",
        files={
            "copier.yml": _make_single_layer_yml("project_name"),
            "template/col1_out.txt.jinja": "col1={{ project_name }}\n",
        },
    )
    collision_2 = build_template_repo(
        tmp_path / "org2" / "mymod",
        files={
            "copier.yml": _make_single_layer_yml("project_name"),
            "template/col2_out.txt.jinja": "col2={{ project_name }}\n",
        },
    )
    return MultiTemplateSet(
        tpl_a=tpl_a,
        tpl_b=tpl_b,
        tpl_c=tpl_c,
        tpl_d=tpl_d,
        tpl_e=tpl_e,
        tpl_f=tpl_f,
        collision_1=collision_1,
        collision_2=collision_2,
    )


# --------------------------------------------------------------------------- #
# spec 006: upgrade fixtures                                                   #
# --------------------------------------------------------------------------- #


def bump_template_repo(
    repo: Path,
    *,
    files: dict[str, str],
    tag: str,
) -> None:
    """Add a second (or later) tagged commit to an existing template repo.

    Writes/overwrites ``files`` on top of the current working tree and commits
    them as a new tag.  Used to simulate a v1.0.0 → v1.1.0 template bump.
    The caller keeps the same ``TemplateRepo`` object; only the git history grows.
    """
    for rel, body in files.items():
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"bump to {tag}")
    _git(repo, "tag", tag)


@dataclass(frozen=True)
class UpgradeFixture:
    """Single-template upgrade fixture: one template with v1.0.0 and v1.1.0."""

    repo: TemplateRepo  # .tag is still "v1.0.0" (initial); v1.1.0 is the bump
    repo_path: Path


@pytest.fixture
def single_upgrade_fixture(tmp_path: Path) -> UpgradeFixture:
    """Template repo with v1.0.0 and v1.1.0.

    v1.0.0: renders hello.txt; ships the answers-file template.
    v1.1.0: adds new_file.txt + a _migrations entry that creates .migrated.
    """
    repo_root = tmp_path / "tpl-upgrade"
    copier_v1 = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        """
    )
    repo = build_template_repo(
        repo_root,
        files={
            "copier.yml": copier_v1,
            "template/hello.txt.jinja": "hello {{ project_name }}\n",
        },
        tag="v1.0.0",
    )
    # v1.1.0: adds new_file.txt + migration entry
    copier_v2 = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        _migrations:
          - command: "touch .migrated"
            version: "v1.1.0"
        """
    )
    bump_template_repo(
        repo_root,
        files={
            "copier.yml": copier_v2,
            "template/hello.txt.jinja": "hello {{ project_name }}\n",
            "template/new_file.txt.jinja": "added in v1.1.0\n",
        },
        tag="v1.1.0",
    )
    return UpgradeFixture(repo=repo, repo_path=repo_root)


@pytest.fixture
def deprecated_migrations_fixture(tmp_path: Path) -> TemplateRepo:
    """Template with the deprecated before/after dict form in _migrations.

    Should be refused by _check_migrations_format before run_update is called.
    """
    repo_root = tmp_path / "tpl-deprecated-migrations"
    copier_yml = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        _migrations:
          - version: "v1.1.0"
            before:
              - "echo before"
            after:
              - "echo after"
        """
    )
    return build_template_repo(
        repo_root,
        files={
            "copier.yml": copier_yml,
            "template/hello.txt.jinja": "hello {{ project_name }}\n",
        },
        tag="v1.0.0",
    )


@dataclass(frozen=True)
class MultiUpgradeFixture:
    """Two-template upgrade fixture: A (no deps) + B (depends_on A), both v1.0.0/v1.1.0."""

    tpl_a_path: Path
    tpl_b_path: Path
    tpl_a_tag_v1: str = "v1.0.0"
    tpl_b_tag_v1: str = "v1.0.0"


@pytest.fixture
def multi_upgrade_fixture(tmp_path: Path) -> MultiUpgradeFixture:
    """Two templates A (no deps) + B (depends_on A); both have v1.0.0 and v1.1.0."""
    a_root = tmp_path / "tpl-mu-a"
    b_root = tmp_path / "tpl-mu-b"

    copier_a_v1 = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        """
    )
    build_template_repo(
        a_root,
        files={
            "copier.yml": copier_a_v1,
            "template/a_out.txt.jinja": "a={{ project_name }}\n",
        },
        tag="v1.0.0",
    )
    bump_template_repo(
        a_root,
        files={"template/a_out.txt.jinja": "a={{ project_name }} v1.1\n"},
        tag="v1.1.0",
    )

    copier_b_v1 = dedent(
        """\
        project_name:
          type: str
        depends_on:
          type: yaml
          default: ["tpl-mu-a"]
          when: false
        _subdirectory: template
        """
    )
    build_template_repo(
        b_root,
        files={
            "copier.yml": copier_b_v1,
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
        tag="v1.0.0",
    )
    bump_template_repo(
        b_root,
        files={"template/b_out.txt.jinja": "b={{ project_name }} v1.1\n"},
        tag="v1.1.0",
    )
    return MultiUpgradeFixture(tpl_a_path=a_root, tpl_b_path=b_root)


@dataclass(frozen=True)
class NewDepUpgradeFixture:
    """Single template that gains a depends_on edge in v1.1.0.

    Used to test Q-006b: refuse when upgraded template declares a new dep not in
    the project.
    """

    tpl_b_path: Path  # The template gaining the new dependency in v1.1.0
    tpl_c_path: Path  # The new dependency (a separate template, NOT in the project)


@pytest.fixture
def new_dep_upgrade_fixture(tmp_path: Path) -> NewDepUpgradeFixture:
    """Template B gains depends_on C in v1.1.0; C is not in the project."""
    b_root = tmp_path / "tpl-nd-b"
    c_root = tmp_path / "tpl-nd-c"

    # Build C first so it exists as a valid template
    build_template_repo(
        c_root,
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/c_out.txt.jinja": "c={{ project_name }}\n",
        },
        tag="v1.0.0",
    )

    copier_b_v1 = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        """
    )
    build_template_repo(
        b_root,
        files={
            "copier.yml": copier_b_v1,
            "template/b_out.txt.jinja": "b={{ project_name }}\n",
        },
        tag="v1.0.0",
    )
    # v1.1.0: adds depends_on C
    copier_b_v2 = dedent(
        """\
        project_name:
          type: str
        depends_on:
          type: yaml
          default: ["tpl-nd-c"]
          when: false
        _subdirectory: template
        """
    )
    bump_template_repo(
        b_root,
        files={"copier.yml": copier_b_v2},
        tag="v1.1.0",
    )
    return NewDepUpgradeFixture(tpl_b_path=b_root, tpl_c_path=c_root)


@dataclass(frozen=True)
class ConflictUpgradeFixture:
    """Template where v1.0.0→v1.1.0 changes a line also edited locally."""

    repo_path: Path


@pytest.fixture
def conflict_upgrade_fixture(tmp_path: Path) -> ConflictUpgradeFixture:
    """Template v1.0.0 renders hello.txt='line1'; v1.1.0 changes it to 'changed_line1'.

    The project will also edit hello.txt to 'local_edit', producing a 3-way conflict.
    """
    repo_root = tmp_path / "tpl-conflict"
    copier_v1 = dedent(
        """\
        project_name:
          type: str
        _subdirectory: template
        """
    )
    build_template_repo(
        repo_root,
        files={
            "copier.yml": copier_v1,
            "template/hello.txt.jinja": "line1\n",
        },
        tag="v1.0.0",
    )
    # v1.1.0: changes hello.txt
    bump_template_repo(
        repo_root,
        files={"template/hello.txt.jinja": "changed_line1\n"},
        tag="v1.1.0",
    )
    return ConflictUpgradeFixture(repo_path=repo_root)


def make_multi_run_spec(
    dest: Path,
    layers: list[tuple[str, TemplateRepo, dict]],
) -> dict:
    """Return a multi-template run-spec dict (suitable for JSON/YAML serialisation).

    ``layers`` is a list of ``(full_id, repo, answers)`` triples.  The selection
    is emitted in the order given; the ordering module will reorder it.
    """
    return {
        "dest": str(dest),
        "selection": [
            {
                "full_id": full_id,
                "source": repo.url,
                "ref": repo.tag,
                "answers": answers,
            }
            for full_id, repo, answers in layers
        ],
    }


# --------------------------------------------------------------------------- #
# spec 009 Phase 0: bailiff-mod-base + bailiff-mod-python module fixtures          #
#                                                                             #
# These build hermetic local git repos from the REAL authored templates under #
# templates/bailiff-mod-{base,python}/, but swap the network/tool `_tasks`       #
# (gitnr/gh/uv preflight) for deterministic OFFLINE stubs so the suite stays   #
# hermetic (Constitution VII / T016 / T023). All RENDERED content (dir         #
# scaffold, AGENTS.md, pyproject.toml, answers file) is copied verbatim — only #
# the task side-effects are stubbed, keeping the render surface faithful.      #
# --------------------------------------------------------------------------- #

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULES_DIR = _REPO_ROOT / "templates"

# Offline stub tasks for bailiff-mod-base: reproduce the task OUTPUTS deterministically
# without touching the network or requiring gitnr/gh. Mirrors the real tasks'
# lifecycle: .gitignore + LICENSE are task-output (guarded/idempotent), git init +
# optional commit run last. The `test -f` / `git init` idempotency guards match the
# real template so reproduce is a no-op re-run (US3 / T027).
_BASE_STUB_TASKS = dedent(
    """\
    _tasks:
      # Stub gitnr: write a deterministic .gitignore marker (no stack union — spec 014).
      - >-
        test -f .bailiff-base-init-done ||
        test -f .gitignore ||
        printf '# stub gitignore\\n' > .gitignore
      # Stub gh LICENSE fetch: guarded, idempotent, offline.
      - >-
        test -f LICENSE ||
        printf '%s License\\nCopyright (c) %s %s\\n'
        '{{ license }}' '{{ (today or "2026")[:4] }}' '{{ copyright_name }}'
        > LICENSE
      - command: "git init --quiet"
        when: "{{ run_git_init }}"
      # extra_dirs MANAGED: idempotent mkdir on every run (init + reproduce).
      - >-
        {% if extra_dirs %}
        for _d in {{ extra_dirs | map('string') | join(' ') }}; do
        mkdir -p "$_d" && touch "$_d/.gitkeep"; done
        {% else %}
        true
        {% endif %}
      # Sentinel: marks tree as init-done so gitnr stub skips on reproduce.
      - "test -f .bailiff-base-init-done || touch .bailiff-base-init-done"
      - command: >-
          git -c user.name=bailiff -c user.email=bailiff@localhost -c commit.gpgsign=false add -A &&
          git -c user.name=bailiff -c user.email=bailiff@localhost -c commit.gpgsign=false commit
          -qm "Initial project scaffold (bailiff-mod-base)"
        when: "{{ initial_commit and run_git_init }}"
    """
)


# Offline stub tasks for bailiff-mod-python (uv variant, spec 011 / v1.0.0).
# Stubs out the mise preflight, mise install (init-only-guarded sentinel), and
# the native uv init (TASK-OUTPUT: writes a minimal stub pyproject.toml if not
# already present, matching the guarded `test -f pyproject.toml ||` lifecycle).
def _python_stub_tasks(pkg_manager: str = "uv") -> str:
    """Generate offline stub tasks for bailiff-mod-python.

    Stubs mise preflight sentinel + native init (uv/pdm).  The project name is
    threaded from the frozen ``project_name`` answer, matching the real init guard.
    """
    # Jinja filter chain for the project name — must match what the real uv/pdm
    # init does when it normalises the name.  Kept in a separate variable to stay
    # within the repo's 100-char line-length limit.
    _name_expr = (
        '{{ project_name | default("project", true)'
        ' | lower | replace(" ", "-") | replace("_", "-") }}'
    )
    # NOTE: the double-quotes below are LITERAL inside printf's single-quoted
    # format string — they must NOT be backslash-escaped. `\"` is an unspecified
    # printf escape: bash strips the backslash, but dash (Ubuntu CI's /bin/sh via
    # subprocess shell=True) keeps it, yielding `name = \"x\"` and failing the
    # assertions. Literal `"` renders identically in both shells.
    _pyproject_printf = (
        "printf "
        f'\'[project]\\\\nname = "{_name_expr}"\\\\n'
        'version = "0.1.0"\\\\n'
        'requires-python = ">={{ python_version }}"\\\\n'
        "dependencies = []\\\\n'"
        " > pyproject.toml"
    )
    return (
        "_tasks:\n"
        "  - \"printf 'mise-preflight-ok\\n' > .bailiff-python-mise-installed\"\n"
        "  - >-\n"
        f"    test -f pyproject.toml ||\n"
        f"    {_pyproject_printf}\n"
    )


# Pre-built stub strings — used by fixtures so each fixture call doesn't rebuild.
_PYTHON_STUB_TASKS = _python_stub_tasks("uv")

# Offline stub tasks for bailiff-mod-apm (spec 007 / T010): swap the real network
# `uvx --from apm-cli==<ver> apm install` for a deterministic OFFLINE no-op. The
# preflight writes a marker; the guarded "install" writes a stub apm.lock.yaml
# from the frozen apm_packages so the suite exercises the real lifecycle
# (task-output lock as external state, guarded on the non-empty set) without a
# network call or the apm CLI. The rendered apm.yml is copied verbatim — only the
# task side-effects are stubbed, keeping the render surface faithful.
_APM_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'apm-preflight-ok\\n' > .bailiff-apm-preflight"
      - command: >-
          printf 'lockfile_version: stub\\napm_version: {{ apm_cli_version }}\\n'
          > apm.lock.yaml
        when: "{{ apm_packages | length > 0 }}"
    """
)


# PDM variant stub — same lifecycle, different pkg_manager label in sentinel content.
_PDM_STUB_TASKS = _python_stub_tasks("pdm")

# Offline stub tasks for bailiff-mod-typescript (bun variant).
_BUN_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'bun-preflight-ok\\n' > .bailiff-ts-preflight"
    """
)

# Offline stub tasks for bailiff-mod-typescript (pnpm variant).
_PNPM_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'pnpm-preflight-ok\\n' > .bailiff-ts-preflight"
    """
)

# Offline stub tasks for bailiff-mod-rust: the cargo new preflight is a no-op marker.
_CARGO_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'cargo-preflight-ok\\n' > .bailiff-rust-preflight"
    """
)

# Offline stub tasks for bailiff-mod-go: the go mod init preflight is a no-op marker.
_GO_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'go-preflight-ok\\n' > .bailiff-go-preflight"
    """
)

# Offline stub tasks for bailiff-mod-terraform: the terraform/tofu init preflight is a no-op marker.
_TERRAFORM_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'terraform-preflight-ok\\n' > .bailiff-terraform-preflight"
    """
)

# Offline stub tasks for bailiff-mod-terraform (opentofu variant).
_TOFU_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'tofu-preflight-ok\\n' > .bailiff-terraform-preflight"
    """
)

# Offline stub tasks for bailiff-mod-cdk: the cdk init preflight is a no-op marker.
_CDK_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'cdk-preflight-ok\\n' > .bailiff-cdk-preflight"
    """
)

# Offline stub tasks for modules that call the AWS CLI.
_AWS_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'aws-preflight-ok\\n' > .bailiff-aws-preflight"
    """
)

# Offline stub tasks for bailiff-mod-cloudformation: preserve the SEED-ONCE
# parameter-seeding loop (offline, no AWS) and stub the opt-in validate task
# with a conditional marker so aws_validate=true/false tests both work.
_CFN_STUB_TASKS = dedent(
    """\
    _tasks:
      # Seed per-env parameter files with test -f guards (identical to the real task,
      # but no network — the loop body is purely offline JSON writes).
      - >-
        mkdir -p "{{ placement_dir }}/parameters" &&
        for env in {{ environment_names | join(" ") }}; do
        test -f "{{ placement_dir }}/parameters/${env}.json" ||
        printf '[{\\n  "ParameterKey": "Environment",\\n  "ParameterValue": "%s"\\n}]\\n' "${env}"
        > "{{ placement_dir }}/parameters/${env}.json";
        done
      # Stub aws validate-template: write marker only when aws_validate=true.
      - command: "printf 'aws-preflight-ok\\\\n' > .bailiff-aws-preflight"
        when: "{{ aws_validate }}"
    """
)

# Offline stub tasks for modules that invoke gh (GitHub CLI).
_GH_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'gh-preflight-ok\\n' > .bailiff-gh-preflight"
    """
)

# Offline stub tasks for modules that invoke the claude CLI (agentic).
_CLAUDE_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'claude-preflight-ok\\n' > .bailiff-claude-preflight"
    """
)

# Offline stub tasks for modules that invoke mise (tool version manager).
_MISE_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'mise-preflight-ok\\n' > .bailiff-mise-preflight"
    """
)

# Offline stub tasks for modules that invoke glab (GitLab CLI) — spec 012.
_GLAB_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'glab-preflight-ok\\n' > .bailiff-glab-preflight"
    """
)

# Offline stub tasks for bailiff-mod-cocogitto (spec 012): mise/cog preflight marker.
_COG_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'cog-preflight-ok\\n' > .bailiff-cocogitto-preflight"
    """
)

# Offline stub tasks for bailiff-mod-moon (spec 012): mise/moon preflight marker.
_MOON_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'moon-preflight-ok\\n' > .bailiff-moon-preflight"
    """
)

# Offline stub tasks for modules that invoke pre-commit (hook manager).
_PRECOMMIT_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'pre-commit-preflight-ok\\n' > .bailiff-precommit-preflight"
    """
)

def _copy_module_with_stub_tasks(
    module_name: str,
    dest_root: Path,
    stub_tasks_yaml: str,
    *,
    tag: str = "v1.0.0",
) -> TemplateRepo:
    """Clone the authored module tree into a tagged git repo, replacing its `_tasks`.

    The rendered subtree (``template/``) is copied verbatim; only the ``_tasks:``
    block in ``copier.yml`` is swapped for the hermetic ``stub_tasks_yaml`` so no
    network/tool is needed. Everything else (questions, edges, _skip_if_exists,
    _subdirectory) is preserved so the fixture exercises the real render surface.
    """
    import re
    import shutil

    src = _MODULES_DIR / module_name
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_root, dirs_exist_ok=True)

    copier_yml = dest_root / "copier.yml"
    text = copier_yml.read_text()
    # Strip the authored `_tasks:` block (from `_tasks:` to EOF — it is the last
    # block in both authored modules) and append the stub tasks.
    text = re.sub(r"\n_tasks:.*\Z", "\n", text, flags=re.DOTALL)
    text = text.rstrip() + "\n\n" + stub_tasks_yaml
    copier_yml.write_text(text)

    _git(dest_root, "init", "-q")
    _git(dest_root, "add", "-A")
    _git(dest_root, "commit", "-qm", "module")
    _git(dest_root, "tag", tag)
    return TemplateRepo(path=dest_root, tag=tag)


@pytest.fixture
def bailiff_mod_base(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-base template as a hermetic repo (tasks stubbed offline)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-base", tmp_path / "bailiff-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_python(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-python template as a hermetic repo (uv/mise tasks stubbed)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-python", tmp_path / "bailiff-mod-python", _PYTHON_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_python_pdm(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-python template with python_pkg_manager=pdm tasks stubbed."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-python", tmp_path / "bailiff-mod-python-pdm", _PDM_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_go(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-go template as a hermetic repo (go preflight stubbed).

    spec 011 T008: renders the real Go overlay surface; the native `go mod init`
    task is replaced with a deterministic offline stub that writes a marker, keeping
    the suite hermetic (no go toolchain required).
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-go", tmp_path / "bailiff-mod-go", _GO_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_apm(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-apm template as a hermetic repo (apm install stubbed offline).

    spec 007 / T010: renders the real apm.yml surface; the network `apm install`
    task is replaced with a deterministic offline stub that writes a marker and a
    stub apm.lock.yaml (external state) from the frozen apm_packages.
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-apm", tmp_path / "bailiff-mod-apm", _APM_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_rust(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-rust template as a hermetic repo (cargo new stubbed offline).

    spec 011: renders the real rust surface; the `cargo new` task is replaced with a
    deterministic offline stub that writes a marker so the suite stays hermetic
    (Constitution VII). The managed rust-toolchain.toml and rustfmt.toml are copied
    verbatim; only the task side-effects are stubbed.
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-rust", tmp_path / "bailiff-mod-rust", _CARGO_STUB_TASKS
    )


# Minimal STUB base layer (spec 007 Q5 / FR-007): provides project_name for
# [stub_base, bailiff-mod-apm] multi-layer tests WITHOUT a hard dependency on
# bailiff-mod-base. It is a plain identity template with a hermetic git-init
# task and the answers-file marker, mirroring the exemplar shape.
#
# Ordering is expressed via `depends_on` only (FR-019/R7 dropped run_before/
# run_after). stub-base carries no depends_on edges; tests that require a
# specific stub-base → apm order must declare the edge on the consuming side.
_APM_STUB_BASE_YML = dedent(
    """\
    project_name:
      type: str
    today:
      type: str
      default: ""
    depends_on:
      type: yaml
      default: []
      when: false
    _subdirectory: template
    _tasks:
      - "git init --quiet"
    """
)


# Offline stub tasks for bailiff-mod-package-add: the path-traversal guard is
# preserved verbatim (SEC-001 — exit 1 on bad input), the monorepo gate is
# preserved, but native tool calls (bun/pnpm/uv/cargo/go) are replaced with a
# deterministic marker write. This keeps the guard logic hermetically testable
# without requiring any language toolchain on the CI host.
# Stub tasks use _external_data.base.layout and _external_data.ts.js_pkg_manager
# (spec 014 FR-004). Tests must pre-seed .copier-answers.bailiff-mod-base.yml and
# .copier-answers.bailiff-mod-ts.yml in dest before calling _init.
_PACKAGE_ADD_STUB_TASKS = dedent(
    r"""
    _tasks:
      # Monorepo gate (no-op when layout != monorepo — same as real task 1).
      - command: >-
          if [ "{{ _external_data.base.layout }}" != "monorepo" ]; then exit 0; fi
        when: "{{ _external_data.base.layout != 'monorepo' }}"
      # Path-traversal guard (SEC-001) — preserved verbatim from the real template.
      # Exits 1 on bad input before any mkdir; no side effects on traversal attempts.
      - command: >-
          if [ "{{ _external_data.base.layout }}" != "monorepo" ]; then exit 0; fi;
          name="{{ name }}";
          dir="{{ dir }}";
          err() { echo "pkg-add: $1" >&2; exit 1; };
          [ -z "$name" ] && err "name must not be empty";
          [ -z "$dir" ] && err "dir must not be empty";
          printf '%s' "$name" | grep -qE '(^$|/|\\|\.\.|^\.$)' && err "name unsafe";
          printf '%s' "$dir" | grep -qE '(\\|/\.\./|/\.\.$|^\.\./|^\.$|^\.\.$)' && err "dir unsafe";
          true
      # Stub scaffold + registration: mkdir + marker (no native tool invocation).
      - command: >-
          if [ "{{ _external_data.base.layout }}" != "monorepo" ]; then exit 0; fi;
          mkdir -p "{{ dir.rstrip('/') }}/{{ name }}";
          printf 'package-add-ok lang={{ lang }} name={{ name }}\\n'
          > .bailiff-package-add-preflight
    """
)

# bailiff-mod-stack-adr has no native-tool tasks (pure template, no tool prerequisite).
# The stub is a no-op marker so _copy_module_with_stub_tasks has a non-empty block
# to append (the regex only strips if _tasks already exists in copier.yml).
_STACK_ADR_STUB_TASKS = dedent(
    """\
    _tasks: []
    """
)


@pytest.fixture
def bailiff_mod_package_add(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-package-add template as a hermetic repo (native tools stubbed).

    SEC-001: path-traversal guard is preserved in the stub so tests can assert
    guard rejection with zero side effects. Native add/init calls replaced with
    a deterministic marker write (offline-safe).
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-package-add",
        tmp_path / "bailiff-mod-package-add",
        _PACKAGE_ADD_STUB_TASKS,
    )


@pytest.fixture
def bailiff_mod_cdk(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-cdk template as a hermetic repo (cdk init stubbed offline)."""
    return _copy_module_with_stub_tasks(
        "bailiff-mod-cdk", tmp_path / "bailiff-mod-cdk", _CDK_STUB_TASKS
    )


@pytest.fixture
def bailiff_mod_cloudformation(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-cloudformation template with AWS tasks stubbed offline.

    The CFN-specific stub preserves the parameter-seeding loop (SEED-ONCE, test -f
    guarded) and replaces only the aws validate-template call with a conditional
    marker so aws_validate=true/false tests both work without AWS credentials.
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-cloudformation",
        tmp_path / "bailiff-mod-cloudformation",
        _CFN_STUB_TASKS,
    )


@pytest.fixture
def bailiff_mod_stack_adr(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-stack-adr template as a hermetic repo (no-op tasks stub).

    spec 011 T013: pure template module; no network or tool tasks to stub.
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-stack-adr", tmp_path / "bailiff-mod-stack-adr", _STACK_ADR_STUB_TASKS
    )


@pytest.fixture
def apm_stub_base(tmp_path: Path) -> TemplateRepo:
    """A minimal stub base layer that threads project_name into bailiff-mod-apm (Q5)."""
    return build_template_repo(
        tmp_path / "bailiff-mod-stub-base",
        files={
            "copier.yml": _APM_STUB_BASE_YML,
            "template/base_out.txt.jinja": "base={{ project_name }}\n",
        },
    )


@pytest.fixture
def bailiff_mod_precommit(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-precommit template as a hermetic repo (install task stubbed).

    `pre-commit install` is replaced with a deterministic offline stub that writes
    a marker file (.bailiff-precommit-preflight) so tests never require the hook
    manager binary on PATH. The rendered hook config (.pre-commit-config.yaml) is
    copied verbatim — only the side-effecting install task is stubbed.
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-precommit", tmp_path / "bailiff-mod-precommit", _PRECOMMIT_STUB_TASKS
    )


# Offline stub tasks for bailiff-mod-agentic (spec 011): swap the real network/tool
# tasks (mise preflight, uvx/apm install, claude plugin install) for deterministic
# OFFLINE no-ops. Stubs write markers so tests can assert task execution paths
# without requiring live CLI tools or network access. The rendered template
# surface (settings.json, .mcp.json, opencode.json, .codex/config.toml, etc.)
# is copied verbatim — only the task side-effects are stubbed.
_AGENTIC_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'mise-preflight-ok\\n' > .bailiff-agentic-preflight"
      - command: "printf 'uvx-preflight-ok\\n' >> .bailiff-agentic-preflight"
        when: "{{ install_via_apm }}"
      - command: "printf 'claude-plugin-install-ok\\n' > .bailiff-claude-plugin-install"
        when: "{{ native_marketplace and 'claude' in agentic_targets
          and agentic_plugins | length > 0 }}"
      - command: >-
          printf 'lockfile_version: stub\\napm_version: {{ apm_cli_version }}\\n'
          > apm.lock.yaml
        when: "{{ install_via_apm and apm_packages | length > 0 }}"
    """
)


@pytest.fixture
def bailiff_mod_agentic(tmp_path: Path) -> TemplateRepo:
    """The real bailiff-mod-agentic template as a hermetic repo (all tasks stubbed offline).

    spec 011 / T014: renders the real per-target config surface; the network/tool
    tasks (mise/uvx preflight, claude plugin install, apm install) are replaced with
    deterministic offline stubs that write markers so tests can assert execution paths.
    """
    return _copy_module_with_stub_tasks(
        "bailiff-mod-agentic", tmp_path / "bailiff-mod-agentic", _AGENTIC_STUB_TASKS
    )
