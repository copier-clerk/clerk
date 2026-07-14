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

    Stands in for `clerk-template-example` in hermetic tests.
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
    from clerk.catalog import TemplateRecord

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
# spec 009 Phase 0: clerk-mod-base + clerk-mod-python module fixtures          #
#                                                                             #
# These build hermetic local git repos from the REAL authored templates under #
# templates/clerk-mod-{base,python}/, but swap the network/tool `_tasks`       #
# (gitnr/gh/uv preflight) for deterministic OFFLINE stubs so the suite stays   #
# hermetic (Constitution VII / T016 / T023). All RENDERED content (dir         #
# scaffold, AGENTS.md, pyproject.toml, answers file) is copied verbatim — only #
# the task side-effects are stubbed, keeping the render surface faithful.      #
# --------------------------------------------------------------------------- #

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULES_DIR = _REPO_ROOT / "templates"

# Offline stub tasks for clerk-mod-base: reproduce the task OUTPUTS deterministically
# without touching the network or requiring gitnr/gh. Mirrors the real tasks'
# lifecycle: .gitignore + LICENSE are task-output (guarded/idempotent), git init +
# optional commit run last. The `test -f` / `git init` idempotency guards match the
# real template so reproduce is a no-op re-run (US3 / T027).
_BASE_STUB_TASKS = dedent(
    """\
    _tasks:
      # Stub gitnr: write a deterministic .gitignore marker recording the stack.
      - >-
        test -f .clerk-base-init-done ||
        test -f .gitignore ||
        printf '# stub gitignore\\nstack={{ gitignore_stack | join(",") }}\\n' > .gitignore
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
      - "test -f .clerk-base-init-done || touch .clerk-base-init-done"
      - command: >-
          git -c user.name=clerk -c user.email=clerk@localhost -c commit.gpgsign=false add -A &&
          git -c user.name=clerk -c user.email=clerk@localhost -c commit.gpgsign=false commit
          -qm "Initial project scaffold (clerk-mod-base)"
        when: "{{ initial_commit and run_git_init }}"
    """
)


# Offline stub tasks for clerk-mod-python (uv variant, spec 011 / v1.0.0).
# Stubs out the mise preflight, mise install (init-only-guarded sentinel), and
# the native uv init (TASK-OUTPUT: writes a minimal stub pyproject.toml if not
# already present, matching the guarded `test -f pyproject.toml ||` lifecycle).
def _python_stub_tasks(pkg_manager: str = "uv") -> str:
    """Generate offline stub tasks for clerk-mod-python.

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
    _pyproject_printf = (
        "printf "
        f'\'[project]\\\\nname = \\"{_name_expr}\\"\\\\n'
        'version = \\"0.1.0\\"\\\\n'
        'requires-python = \\">={{ python_version }}\\"\\\\n'
        "dependencies = []\\\\n'"
        " > pyproject.toml"
    )
    return (
        "_tasks:\n"
        "  - \"printf 'mise-preflight-ok\\n' > .clerk-python-mise-installed\"\n"
        "  - >-\n"
        f"    test -f pyproject.toml ||\n"
        f"    {_pyproject_printf}\n"
    )


# Pre-built stub strings — used by fixtures so each fixture call doesn't rebuild.
_PYTHON_STUB_TASKS = _python_stub_tasks("uv")

# Offline stub tasks for clerk-mod-apm (spec 007 / T010): swap the real network
# `uvx --from apm-cli==<ver> apm install` for a deterministic OFFLINE no-op. The
# preflight writes a marker; the guarded "install" writes a stub apm.lock.yaml
# from the frozen apm_packages so the suite exercises the real lifecycle
# (task-output lock as external state, guarded on the non-empty set) without a
# network call or the apm CLI. The rendered apm.yml is copied verbatim — only the
# task side-effects are stubbed, keeping the render surface faithful.
_APM_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'apm-preflight-ok\\n' > .clerk-apm-preflight"
      - command: >-
          printf 'lockfile_version: stub\\napm_version: {{ apm_cli_version }}\\n'
          > apm.lock.yaml
        when: "{{ apm_packages | length > 0 }}"
    """
)


# PDM variant stub — same lifecycle, different pkg_manager label in sentinel content.
_PDM_STUB_TASKS = _python_stub_tasks("pdm")

# Offline stub tasks for clerk-mod-typescript (bun variant).
_BUN_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'bun-preflight-ok\\n' > .clerk-ts-preflight"
    """
)

# Offline stub tasks for clerk-mod-typescript (pnpm variant).
_PNPM_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'pnpm-preflight-ok\\n' > .clerk-ts-preflight"
    """
)

# Offline stub tasks for clerk-mod-rust: the cargo new preflight is a no-op marker.
_CARGO_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'cargo-preflight-ok\\n' > .clerk-rust-preflight"
    """
)

# Offline stub tasks for clerk-mod-go: the go mod init preflight is a no-op marker.
_GO_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'go-preflight-ok\\n' > .clerk-go-preflight"
    """
)

# Offline stub tasks for clerk-mod-terraform: the terraform/tofu init preflight is a no-op marker.
_TERRAFORM_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'terraform-preflight-ok\\n' > .clerk-terraform-preflight"
    """
)

# Offline stub tasks for clerk-mod-terraform (opentofu variant).
_TOFU_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'tofu-preflight-ok\\n' > .clerk-terraform-preflight"
    """
)

# Offline stub tasks for clerk-mod-cdk: the cdk init preflight is a no-op marker.
_CDK_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'cdk-preflight-ok\\n' > .clerk-cdk-preflight"
    """
)

# Offline stub tasks for modules that call the AWS CLI.
_AWS_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'aws-preflight-ok\\n' > .clerk-aws-preflight"
    """
)

# Offline stub tasks for modules that invoke gh (GitHub CLI).
_GH_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'gh-preflight-ok\\n' > .clerk-gh-preflight"
    """
)

# Offline stub tasks for modules that invoke the claude CLI (agentic).
_CLAUDE_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'claude-preflight-ok\\n' > .clerk-claude-preflight"
    """
)

# Offline stub tasks for modules that invoke mise (tool version manager).
_MISE_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'mise-preflight-ok\\n' > .clerk-mise-preflight"
    """
)

# Offline stub tasks for modules that invoke pre-commit (hook manager).
_PRECOMMIT_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'pre-commit-preflight-ok\\n' > .clerk-precommit-preflight"
    """
)

# Offline stub tasks for modules that invoke lefthook (hook manager).
_LEFTHOOK_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'lefthook-preflight-ok\\n' > .clerk-precommit-preflight"
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
def clerk_mod_base(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-base template as a hermetic repo (tasks stubbed offline)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-base", tmp_path / "clerk-mod-base", _BASE_STUB_TASKS
    )


@pytest.fixture
def clerk_mod_python(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-python template as a hermetic repo (uv/mise tasks stubbed)."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-python", tmp_path / "clerk-mod-python", _PYTHON_STUB_TASKS
    )


@pytest.fixture
def clerk_mod_python_pdm(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-python template with python_pkg_manager=pdm tasks stubbed."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-python", tmp_path / "clerk-mod-python-pdm", _PDM_STUB_TASKS
    )
def clerk_mod_go(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-go template as a hermetic repo (go preflight stubbed).

    spec 011 T008: renders the real Go overlay surface; the native `go mod init`
    task is replaced with a deterministic offline stub that writes a marker, keeping
    the suite hermetic (no go toolchain required).
    """
    return _copy_module_with_stub_tasks("clerk-mod-go", tmp_path / "clerk-mod-go", _GO_STUB_TASKS)


@pytest.fixture
def clerk_mod_apm(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-apm template as a hermetic repo (apm install stubbed offline).

    spec 007 / T010: renders the real apm.yml surface; the network `apm install`
    task is replaced with a deterministic offline stub that writes a marker and a
    stub apm.lock.yaml (external state) from the frozen apm_packages.
    """
    return _copy_module_with_stub_tasks(
        "clerk-mod-apm", tmp_path / "clerk-mod-apm", _APM_STUB_TASKS
    )


@pytest.fixture
def clerk_mod_rust(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-rust template as a hermetic repo (cargo new stubbed offline).

    spec 011: renders the real rust surface; the `cargo new` task is replaced with a
    deterministic offline stub that writes a marker so the suite stays hermetic
    (Constitution VII). The managed rust-toolchain.toml and rustfmt.toml are copied
    verbatim; only the task side-effects are stubbed.
    """
    return _copy_module_with_stub_tasks(
        "clerk-mod-rust", tmp_path / "clerk-mod-rust", _CARGO_STUB_TASKS
    )


# Minimal STUB base layer (spec 007 Q5 / FR-007): provides the threaded
# project_name for [stub_base, clerk-mod-apm] multi-layer tests WITHOUT a hard
# dependency on clerk-mod-base. It is a plain identity template with a hermetic
# git-init task and the answers-file marker, mirroring the exemplar shape.
#
# It declares run_before: [clerk-mod-apm] so the spec-003 engine sequences it
# BEFORE the apm layer (threading project_name forward). Per Q5, the adjacency is
# declared by the BASE (the module that needs it), never baked into 007's edges.
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
    run_after:
      type: yaml
      default: []
      when: false
    run_before:
      type: yaml
      default: ["clerk-mod-apm"]
      when: false
    _subdirectory: template
    _tasks:
      - "git init --quiet"
    """
)


@pytest.fixture
def apm_stub_base(tmp_path: Path) -> TemplateRepo:
    """A minimal stub base layer that threads project_name into clerk-mod-apm (Q5)."""
    return build_template_repo(
        tmp_path / "clerk-mod-stub-base",
        files={
            "copier.yml": _APM_STUB_BASE_YML,
            "template/base_out.txt.jinja": "base={{ project_name }}\n",
        },
    )


@pytest.fixture
def clerk_mod_precommit(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-precommit template as a hermetic repo (install task stubbed).

    pre-commit install / lefthook install are replaced with a deterministic
    offline stub that writes a marker file (.clerk-precommit-preflight) so tests
    never require the hook manager binary on PATH. The rendered hook config
    (.pre-commit-config.yaml or lefthook.yml) is copied verbatim — only the
    side-effecting install task is stubbed.
    """
    return _copy_module_with_stub_tasks(
        "clerk-mod-precommit", tmp_path / "clerk-mod-precommit", _PRECOMMIT_STUB_TASKS
    )


@pytest.fixture
def clerk_mod_precommit_lefthook(tmp_path: Path) -> TemplateRepo:
    """clerk-mod-precommit with the lefthook install task stubbed offline."""
    return _copy_module_with_stub_tasks(
        "clerk-mod-precommit", tmp_path / "clerk-mod-precommit-lh", _LEFTHOOK_STUB_TASKS
# Offline stub tasks for clerk-mod-agentic (spec 011): swap the real network/tool
# tasks (mise preflight, uvx/apm install, claude plugin install) for deterministic
# OFFLINE no-ops. Stubs write markers so tests can assert task execution paths
# without requiring live CLI tools or network access. The rendered template
# surface (settings.json, .mcp.json, opencode.json, .codex/config.toml, etc.)
# is copied verbatim — only the task side-effects are stubbed.
_AGENTIC_STUB_TASKS = dedent(
    """\
    _tasks:
      - "printf 'mise-preflight-ok\\n' > .clerk-agentic-preflight"
      - command: "printf 'uvx-preflight-ok\\n' >> .clerk-agentic-preflight"
        when: "{{ install_via_apm }}"
      - command: "printf 'claude-plugin-install-ok\\n' > .clerk-claude-plugin-install"
        when: "{{ native_marketplace and 'claude' in agentic_targets
          and agentic_plugins | length > 0 }}"
      - command: >-
          printf 'lockfile_version: stub\\napm_version: {{ apm_cli_version }}\\n'
          > apm.lock.yaml
        when: "{{ install_via_apm and apm_packages | length > 0 }}"
    """
)


@pytest.fixture
def clerk_mod_agentic(tmp_path: Path) -> TemplateRepo:
    """The real clerk-mod-agentic template as a hermetic repo (all tasks stubbed offline).

    spec 011 / T014: renders the real per-target config surface; the network/tool
    tasks (mise/uvx preflight, claude plugin install, apm install) are replaced with
    deterministic offline stubs that write markers so tests can assert execution paths.
    """
    return _copy_module_with_stub_tasks(
        "clerk-mod-agentic", tmp_path / "clerk-mod-agentic", _AGENTIC_STUB_TASKS
    )
