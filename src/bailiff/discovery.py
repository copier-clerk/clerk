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

import re
import shutil
import subprocess
import tempfile
import warnings
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

# The single ``when: false`` edge that carries bailiff's dependency graph (spec 014 FR-019/R7).
# run_after and run_before are DROPPED — depends_on is the only ordering edge.
_EDGE_KEYS = ("depends_on",)

# The hidden ``when: false`` key that carries the post-task list.
_POST_TASKS_KEY = "_post_tasks"

# Phase values; default when absent is "normal".
_VALID_PHASES = frozenset({"pre", "normal", "post"})

# Pattern for a valid _external_data value: .copier-answers.<basename>.yml
# No Jinja ({{ ... }}), no traversal (..), no URL (://), no nested paths.
_EXTERNAL_DATA_PATH_RE = re.compile(r"^\.copier-answers\.([^/\\]+)\.yml$")

# Capability names are kebab-case (spec 013 FR-007); no closed vocabulary.
_CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9-]*$")


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
    provides: list[str] = field(default_factory=list)
    exclusive: bool = False
    # spec 014: alias → producer-basename mapping from _external_data block.
    external_data_aliases: dict[str, str] = field(default_factory=dict)
    # spec 014: deferred tasks declared via _post_tasks (list of command strings).
    post_tasks: list[Any] = field(default_factory=list)
    # spec 014: module execution phase ("pre" | "normal" | "post"); default "normal".
    phase: str = "normal"

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
            "provides": self.provides,
            "exclusive": self.exclusive,
            "external_data_aliases": self.external_data_aliases,
            "post_tasks": self.post_tasks,
            "phase": self.phase,
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
    # has_tasks covers both inline _tasks AND deferred _post_tasks: either can execute
    # arbitrary commands, so both require the same trust gate (spec 014 FR-021/R11).
    has_tasks = bool(raw.get("_tasks")) or bool(raw.get(_POST_TASKS_KEY))
    has_migrations = bool(raw.get("_migrations"))
    provides, exclusive = _read_capabilities(raw, source)
    external_data_aliases = _read_external_data(raw, source)
    post_tasks = _read_post_tasks(raw)
    phase = _read_phase(raw, source)

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
        provides=provides,
        exclusive=exclusive,
        external_data_aliases=external_data_aliases,
        post_tasks=post_tasks,
        phase=phase,
    )


def _read_external_data(raw: dict[str, Any], source: str) -> dict[str, str]:
    """Parse ``_external_data`` → ``{alias: producer_basename}`` (FR-006/R6/R9).

    Each value MUST be a literal ``.copier-answers.<basename>.yml`` (no Jinja
    expressions, no path traversal, no URL).  Non-conforming values raise
    ``DiscoveryError`` for first-party modules — they cannot be validated at
    engine preflight time if the alias→basename mapping is ambiguous.
    """
    raw_ed = raw.get("_external_data")
    if not raw_ed:
        return {}
    if not isinstance(raw_ed, dict):
        raise DiscoveryError(
            f"{source!r}: _external_data must be a mapping of alias → answers-file path, "
            f"got {type(raw_ed).__name__!r}"
        )
    result: dict[str, str] = {}
    for alias, path_val in raw_ed.items():
        if not isinstance(path_val, str):
            raise DiscoveryError(
                f"{source!r}: _external_data[{alias!r}] must be a string path, "
                f"got {type(path_val).__name__!r}"
            )
        # Reject Jinja expressions, path traversal, URLs, nested paths.
        m = _EXTERNAL_DATA_PATH_RE.match(path_val)
        if not m:
            raise DiscoveryError(
                f"{source!r}: _external_data[{alias!r}] value {path_val!r} does not match "
                f"the required format '.copier-answers.<basename>.yml'. "
                f"Jinja expressions, path traversal (..), URLs, and nested paths are not "
                f"allowed. Use a literal basename reference (FR-006a/R9)."
            )
        result[alias] = m.group(1)
    return result


def _read_post_tasks(raw: dict[str, Any]) -> list[Any]:
    """Read ``_post_tasks`` as a list of task commands (FR-021/R11).

    ``_post_tasks`` is declared as a top-level settings key (like ``_tasks``),
    not as a hidden ``when:false`` question. Its value is a list of strings or
    dicts (same shape as ``_tasks``).  Missing or empty → empty list.
    """
    pt = raw.get(_POST_TASKS_KEY)
    if not pt:
        return []
    if isinstance(pt, list):
        return list(pt)
    return []


def _read_phase(raw: dict[str, Any], source: str) -> str:
    """Read ``_bailiff_phase`` settings key; default "normal" when absent (FR-020/R8).

    Warns and falls back to "normal" on an invalid value so third-party modules
    with a typo don't hard-fail (consistent with ``_read_capabilities`` policy).
    """
    phase = raw.get("_bailiff_phase", "normal")
    if not isinstance(phase, str):
        warnings.warn(
            f"{source!r}: _bailiff_phase must be a string ('pre'|'normal'|'post'), "
            f"got {phase!r}; treating as 'normal'",
            stacklevel=2,
        )
        return "normal"
    phase = phase.strip()
    if phase not in _VALID_PHASES:
        warnings.warn(
            f"{source!r}: _bailiff_phase={phase!r} is not a known phase "
            f"({', '.join(sorted(_VALID_PHASES))}); treating as 'normal'",
            stacklevel=2,
        )
        return "normal"
    return phase


def _read_capabilities(raw: dict[str, Any], source: str) -> tuple[list[str], bool]:
    """Statically read ``_bailiff_provides`` / ``_bailiff_exclusive`` (spec 013 FR-007).

    Informational metadata only. Malformed third-party values (non-list provides,
    non-string or non-kebab-case entries, non-bool exclusive) are warned and treated
    as absent — NEVER a hard failure here; well-formedness is enforced for
    first-party modules only, in CI (check_modules.py).
    """
    provides: list[str] = []
    raw_provides = raw.get("_bailiff_provides")
    if raw_provides is not None:
        if not isinstance(raw_provides, list):
            warnings.warn(
                f"{source!r}: _bailiff_provides is not a list "
                f"({raw_provides!r}); treating as absent",
                stacklevel=2,
            )
        else:
            for entry in raw_provides:
                if isinstance(entry, str) and _CAPABILITY_RE.match(entry):
                    provides.append(entry)
                else:
                    warnings.warn(
                        f"{source!r}: _bailiff_provides entry {entry!r} is not a "
                        f"kebab-case string; ignoring it",
                        stacklevel=2,
                    )

    exclusive = False
    raw_exclusive = raw.get("_bailiff_exclusive")
    if raw_exclusive is not None:
        if isinstance(raw_exclusive, bool):
            exclusive = raw_exclusive
        else:
            warnings.warn(
                f"{source!r}: _bailiff_exclusive is not a boolean "
                f"({raw_exclusive!r}); treating as absent",
                stacklevel=2,
            )

    return provides, exclusive


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


def run_post_task(cmd: str, dest: str) -> int:
    """Execute a single post-task command in ``dest`` and return the exit code.

    Lives in ``discovery`` so all subprocess calls remain here and runner.py stays
    subprocess-free (FR-004: secret values must never appear in argv / process listings).
    Post-tasks do not carry secret values — but the structural invariant is maintained.
    """
    result = subprocess.run(cmd, shell=True, cwd=dest, check=False)  # noqa: S602
    return result.returncode


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
