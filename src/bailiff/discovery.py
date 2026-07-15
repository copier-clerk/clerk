"""Static template discovery — bailiff's safe, no-code-execution inspection.

Discovery answers "what does this template ask for, and can it be reproduced?"
WITHOUT running any template-authored code. It does this by cloning the template
at a pinned ref and reading ``copier.yml`` as plain YAML plus globbing the file
tree — it never builds copier's Jinja environment and never imports
``copier.Template``/``Worker`` (which would import template-declared extensions =
arbitrary code execution, and is NOT trust-gated). Consequently discovery is safe
to run against an untrusted source and requires no trust (spec FR-004a).

Question defaults may themselves be Jinja expressions; discovery reports them
**raw / un-rendered** and never evaluates them (FR-004a).

This module deliberately does not depend on copier at all — it is pure ``git`` +
``yaml`` + ``packaging``. Per the constitution (v2.0.0, Principle IV) static
parsing is preferred; resolving ``!include``/inheritance for arbitrary third-party
templates is a later concern (roadmap Q3), not this slice.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from packaging.version import InvalidVersion, Version

from bailiff.errors import BailiffError, DeprecatedMigrationFormatError, DiscoveryError

# copier writes ``.copier-answers.yml`` ONLY if the template ships a file named
# with this Jinja expression (verified). Its absence ⇒ the generated project has
# no recorded answers ⇒ it is unreproducible (Constitution VI / FR-016).
_ANSWERS_FILE_MARKER = "_copier_conf.answers_file"

# copier.yml keys that are settings, not questions.
_SETTINGS_PREFIX = "_"

# The hidden ``when: false`` answers that carry bailiff's dependency graph.
_EDGE_KEYS = ("depends_on", "run_after", "run_before")


@dataclass(frozen=True)
class Question:
    """A single question a template asks (visible, i.e. not a hidden edge)."""

    key: str
    type: str
    choices: list[Any] | None
    default_raw: Any  # reported UN-rendered; may be a Jinja expression string
    help: str | None
    when: Any
    validator: str | None
    secret: bool


@dataclass(frozen=True)
class Discovery:
    """The static description of a template (the ``bailiff discover`` output)."""

    source: str
    ref: str
    versions: list[str]
    reproducible: bool
    has_tasks: bool
    jinja_extensions: list[str]
    questions: list[Question]
    secret_questions: list[str]
    dependency_edges: dict[str, Any] = field(default_factory=dict)
    has_migrations: bool = False

    def to_dict(self) -> dict[str, Any]:
        """The documented, JSON-serializable shape the agent reads (FR-004)."""
        return {
            "source": self.source,
            "ref": self.ref,
            "versions": self.versions,
            "reproducible": self.reproducible,
            "has_tasks": self.has_tasks,
            "has_migrations": self.has_migrations,
            "jinja_extensions": self.jinja_extensions,
            "questions": [
                {
                    "key": q.key,
                    "type": q.type,
                    "choices": q.choices,
                    "default_raw": q.default_raw,
                    "help": q.help,
                    "when": q.when,
                    "validator": q.validator,
                    "secret": q.secret,
                }
                for q in self.questions
            ],
            "secret_questions": self.secret_questions,
            "dependency_edges": self.dependency_edges,
        }


def _git(*args: str) -> str:
    """Run git and return stdout; raise DiscoveryError on failure."""
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise DiscoveryError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def list_versions(source: str) -> list[str]:
    """Return the source's PEP 440-parseable tags, oldest→newest.

    copier silently discards non-PEP-440 tags, so a source with none is unusable
    (FR-016a). We mirror that filter here and expose the usable set.
    """
    out = _git("ls-remote", "--tags", source)
    tags: list[str] = []
    for line in out.splitlines():
        if "refs/tags/" not in line or line.rstrip().endswith("^{}"):
            continue
        tags.append(line.split("refs/tags/", 1)[1].strip())

    valid: list[tuple[Version, str]] = []
    for tag in tags:
        try:
            valid.append((Version(tag.lstrip("v")), tag))
        except InvalidVersion:
            continue  # copier would ignore it; so do we
    valid.sort(key=lambda pair: pair[0])
    return [tag for _, tag in valid]


def discover(source: str, ref: str | None = None) -> Discovery:
    """Inspect one template at ``source`` (optionally pinned to ``ref``).

    Clones shallowly at the resolved ref and reads ``copier.yml`` + the file tree
    statically. Refuses a source with no usable version (FR-016a).
    """
    versions = list_versions(source)
    resolved = ref or (versions[-1] if versions else None)
    if resolved is None:
        raise DiscoveryError(
            f"source has no usable version: {source!r} exposes no PEP 440 tag "
            f"(copier cannot resolve a version to check out)"
        )

    tmp = Path(tempfile.mkdtemp(prefix="bailiff-discover-"))
    try:
        # Shallow clone at the exact ref — no code runs, this is git only.
        _git("clone", "--quiet", "--depth", "1", "--branch", resolved, source, str(tmp))
        return _describe(source, resolved, versions, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _describe(source: str, ref: str, versions: list[str], clone: Path) -> Discovery:
    config_path = clone / "copier.yml"
    if not config_path.exists():
        config_path = clone / "copier.yaml"
    if not config_path.exists():
        raise DiscoveryError(f"no copier.yml/.yaml at the template root of {source!r}")

    # safe_load: no custom constructors, no code execution. A template using
    # copier's `!include` tag would raise here — acceptable for this slice
    # (first-party templates are flat; third-party !include is roadmap Q3).
    try:
        raw = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise DiscoveryError(f"copier.yml is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise DiscoveryError("copier.yml did not parse to a mapping")

    subdirectory = raw.get("_subdirectory", "")
    jinja_extensions = list(raw.get("_jinja_extensions", []) or [])
    has_tasks = bool(raw.get("_tasks"))
    has_migrations = bool(raw.get("_migrations"))

    questions: list[Question] = []
    secret_questions: list[str] = []
    dependency_edges: dict[str, Any] = {}

    # copier exposes secrets two ways: per-question `secret: true` AND a top-level
    # `_secret_questions: [keys]` list.  Both must be parsed so our flag set matches
    # copier's own exclusion set (FR-003b).
    list_form_secrets: set[str] = set(raw.get("_secret_questions") or [])

    for key, spec in raw.items():
        if key.startswith(_SETTINGS_PREFIX):
            continue
        spec = spec if isinstance(spec, dict) else {"type": "str", "default": spec}
        when = spec.get("when")
        is_hidden = when is False or (isinstance(when, str) and when.strip().lower() == "false")

        if key in _EDGE_KEYS and is_hidden:
            dependency_edges[key] = spec.get("default")
            continue  # hidden edges are not questions and are never persisted

        secret = bool(spec.get("secret", False)) or key in list_form_secrets
        if secret and key not in secret_questions:
            secret_questions.append(key)
        questions.append(
            Question(
                key=key,
                type=str(spec.get("type", "str")),
                choices=spec.get("choices"),
                default_raw=spec.get("default"),
                help=spec.get("help"),
                when=when,
                validator=spec.get("validator"),
                secret=secret,
            )
        )

    reproducible = _ships_answers_file(clone, subdirectory)

    return Discovery(
        source=source,
        ref=ref,
        versions=versions,
        reproducible=reproducible,
        has_tasks=has_tasks,
        has_migrations=has_migrations,
        jinja_extensions=jinja_extensions,
        questions=questions,
        secret_questions=secret_questions,
        dependency_edges=dependency_edges,
    )


def _check_migrations_format(raw: dict[str, Any], source: str) -> None:
    """Refuse the deprecated before/after dict form in _migrations (Constitution VI).

    The new format allows: bare string, bare list, or a dict with a 'command' key.
    The deprecated form has a dict entry with 'before' or 'after' keys — that form
    emits DeprecationWarning from copier and is refused here at discovery time.

    Detection is purely static (no copier runtime call); this runs before run_update.
    """
    migrations = raw.get("_migrations")
    if not migrations:
        return
    if not isinstance(migrations, list):
        return
    for entry in migrations:
        if isinstance(entry, dict) and ("before" in entry or "after" in entry):
            raise DeprecatedMigrationFormatError(
                f"template {source!r} uses the deprecated _migrations format "
                f"(entry with 'before'/'after' keys). "
                f"Migrate to the new format: use a 'command' key instead of "
                f"'before'/'after'. See contracts/upgrade.md for the new format."
            )


def check_migrations_format_at_source(source: str, ref: str | None) -> None:
    """Shallow-clone the template at the target ref and check _migrations format.

    Re-clones because Discovery does not expose the raw config dict.  Delegates to
    _check_migrations_format (same static YAML parse).  Lives in discovery so all
    subprocess/git calls remain here and runner.py stays subprocess-free (FR-004:
    secret values must never appear in argv/process listings).
    """
    versions = list_versions(source)
    resolved = ref or (versions[-1] if versions else None)
    if resolved is None:
        return  # no version → discover would have already raised DiscoveryError
    tmp = Path(tempfile.mkdtemp(prefix="bailiff-mig-check-"))
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", resolved, source, str(tmp)],
            capture_output=True,
            check=False,
        )
        config_path = tmp / "copier.yml"
        if not config_path.exists():
            config_path = tmp / "copier.yaml"
        if not config_path.exists():
            return
        try:
            raw = yaml.safe_load(config_path.read_text()) or {}
        except Exception:  # noqa: BLE001
            return
        if isinstance(raw, dict):
            _check_migrations_format(raw, source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _git_identity_configured(dst: Path) -> bool:
    """True if both user.name and user.email are set for the repo at ``dst``."""
    name = subprocess.run(["git", "config", "user.name"], cwd=dst, capture_output=True, text=True)
    email = subprocess.run(["git", "config", "user.email"], cwd=dst, capture_output=True, text=True)
    return bool(name.stdout.strip()) and bool(email.stdout.strip())


def worktree_is_dirty(dest: str) -> bool:
    """True if ``dest`` is a git repo with uncommitted changes (tracked or untracked).

    Used as an upgrade prerequisite: the between-layer commit stages everything
    (``git add -A``), so a real upgrade must start from a clean tree or the user's
    unrelated work would be swept into a bailiff commit. A path that is not a git repo
    returns False (copier surfaces the not-a-repo case itself). Lives in discovery so
    all subprocess/git calls stay here (FR-004).
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=Path(dest),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False  # not a git repo — not our precondition to enforce
    return bool(result.stdout.strip())


def git_commit_if_dirty(dest: str, message: str) -> None:
    """Stage and commit any changes in ``dest`` if the working tree is dirty.

    Required between layers in multi-layer upgrade: copier's run_update refuses
    to run if the destination git repo has uncommitted changes.  Lives in discovery
    so all subprocess calls remain here and runner.py stays subprocess-free (FR-004).

    Uses the repo's configured git identity when present (these are the user's own
    project changes); falls back to a bailiff identity so the between-layer commit still
    succeeds where no identity is configured (CI, fresh containers).  A failed commit
    is raised rather than swallowed — otherwise the next layer's run_update refuses on
    a still-dirty tree with a misleading "repository is dirty" error.
    """
    dst = Path(dest)
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=dst,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return  # not a git repo or already clean
    subprocess.run(["git", "add", "-A"], cwd=dst, capture_output=True, check=False)
    cmd = ["git"]
    if not _git_identity_configured(dst):
        cmd += ["-c", "user.name=bailiff", "-c", "user.email=bailiff@localhost"]
    cmd += ["-c", "commit.gpgsign=false", "commit", "-qm", message]
    commit = subprocess.run(cmd, cwd=dst, capture_output=True, text=True)
    if commit.returncode != 0:
        detail = commit.stderr.strip() or commit.stdout.strip()
        raise BailiffError(
            f"bailiff could not commit intermediate upgrade state in {dest!r} "
            f"between template layers: {detail}"
        )


def _ships_answers_file(clone: Path, subdirectory: str) -> bool:
    """True if the template ships a ``{{ _copier_conf.answers_file }}.jinja`` file.

    Static file-tree check only (no render); this is the reproducibility gate
    (FR-016). The marker substring is matched so a custom ``_answers_file`` name is
    still detected as long as the template renders the answers file.
    """
    search_root = clone / subdirectory if subdirectory else clone
    if not search_root.exists():
        return False
    for path in search_root.rglob("*"):
        if path.is_file() and _ANSWERS_FILE_MARKER in path.name and path.name.endswith(".jinja"):
            return True
    return False
