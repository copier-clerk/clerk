"""Static template discovery — clerk's safe, no-code-execution inspection.

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

from clerk.errors import DiscoveryError

# copier writes ``.copier-answers.yml`` ONLY if the template ships a file named
# with this Jinja expression (verified). Its absence ⇒ the generated project has
# no recorded answers ⇒ it is unreproducible (Constitution VI / FR-016).
_ANSWERS_FILE_MARKER = "_copier_conf.answers_file"

# copier.yml keys that are settings, not questions.
_SETTINGS_PREFIX = "_"

# The hidden ``when: false`` answers that carry clerk's dependency graph.
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
    """The static description of a template (the ``clerk discover`` output)."""

    source: str
    ref: str
    versions: list[str]
    reproducible: bool
    has_tasks: bool
    jinja_extensions: list[str]
    questions: list[Question]
    secret_questions: list[str]
    dependency_edges: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """The documented, JSON-serializable shape the agent reads (FR-004)."""
        return {
            "source": self.source,
            "ref": self.ref,
            "versions": self.versions,
            "reproducible": self.reproducible,
            "has_tasks": self.has_tasks,
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

    tmp = Path(tempfile.mkdtemp(prefix="clerk-discover-"))
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
        jinja_extensions=jinja_extensions,
        questions=questions,
        secret_questions=secret_questions,
        dependency_edges=dependency_edges,
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
