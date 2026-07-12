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
