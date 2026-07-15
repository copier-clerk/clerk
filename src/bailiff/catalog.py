"""User-owned catalog of source repos — static listing, deterministic, no template code.

The catalog is a plain TOML file listing **named catalog pointers**, each with a
set of source locators (``gituser/gitrepo`` or a full URL, with an optional
``@ref`` override).  It is NOT a copier template and nothing catalog-related is
written into any generated project (spec-010 invariant).

Default path: ``user_config_path("bailiff", appauthor=False)/catalog.toml``,
overridable via the ``BAILIFF_CATALOG_PATH`` environment variable or the
``--catalog PATH`` CLI flag — mirroring ``trust.py``'s ``settings_path()``
pattern.

TOML shape::

    [[catalog]]
    name = "demo"
    sources = [
        "bailiff-io/bailiff-template-example",
        "acme/bailiff-mod-python@v2.1.0",   # @ref: display/standardization override only
    ]

Discovery reuses ``discovery.discover(source, ref)`` verbatim — static,
no Jinja env, no code execution, no trust required.  The derived listing is
deterministic: same sources at same pins → identical output (SC-002).
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w
from platformdirs import user_config_path

from bailiff import discovery
from bailiff.errors import CatalogError, DiscoveryError

_ENV_VAR = "BAILIFF_CATALOG_PATH"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def catalog_path() -> Path:
    """Resolve the catalog TOML path (env override → platformdirs default).

    Mirrors ``trust.settings_path()`` so the resolution is consistent with
    other bailiff user-config files.
    """
    env = os.getenv(_ENV_VAR)
    if env:
        return Path(env)
    return user_config_path("bailiff", appauthor=False) / "catalog.toml"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CatalogSource:
    """One source entry in a catalog pointer."""

    locator: str  # the raw gituser/gitrepo or URL (without @ref)
    ref: str | None  # the optional @ref override (display/standardization only)


@dataclass
class CatalogPointer:
    """A named catalog pointer — one namespace for full-ids."""

    name: str
    sources: list[CatalogSource] = field(default_factory=list)


@dataclass
class CatalogModel:
    """In-memory representation of the catalog TOML file."""

    pointers: list[CatalogPointer] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TOML serialisation
# ---------------------------------------------------------------------------


def _parse_source_string(raw: str) -> CatalogSource:
    """Split ``locator[@ref]`` into ``CatalogSource``."""
    if "@" in raw:
        # Split on the last '@' to handle URLs that may contain '@' in host/user.
        # For the standard gituser/gitrepo@ref form this is unambiguous.
        locator, _, ref = raw.rpartition("@")
        return CatalogSource(locator=locator.strip(), ref=ref.strip() or None)
    return CatalogSource(locator=raw.strip(), ref=None)


def _source_to_string(src: CatalogSource) -> str:
    if src.ref:
        return f"{src.locator}@{src.ref}"
    return src.locator


def load(path: Path) -> CatalogModel:
    """Load the catalog from ``path``.

    - Missing file → returns an empty ``CatalogModel`` (NOT an error; callers
      that require the file to exist must check themselves).
    - Malformed TOML → raises ``CatalogError`` (never silently clobbers).
    """
    if not path.is_file():
        return CatalogModel()
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise CatalogError(f"catalog file is not valid TOML: {path}\n  {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError(f"catalog file did not parse to a mapping: {path}")

    pointers: list[CatalogPointer] = []
    for raw_ptr in data.get("catalog", []):
        if not isinstance(raw_ptr, dict):
            raise CatalogError(f"each [[catalog]] entry must be a table: {path}")
        name = raw_ptr.get("name", "")
        if not name:
            raise CatalogError(f"[[catalog]] entry missing 'name': {path}")
        raw_sources = raw_ptr.get("sources", [])
        sources = [_parse_source_string(s) for s in raw_sources]
        pointers.append(CatalogPointer(name=str(name), sources=sources))

    return CatalogModel(pointers=pointers)


def save(path: Path, model: CatalogModel) -> None:
    """Write ``model`` to ``path`` using tomli_w (mkdir -p parent).

    Note: tomli_w does not preserve comments.  This is acceptable because the
    catalog is bailiff-managed config; ``tomlkit`` is the upgrade path if
    comment-preservation is ever required.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog_list = [
        {"name": ptr.name, "sources": [_source_to_string(s) for s in ptr.sources]}
        for ptr in model.pointers
    ]
    data: dict[str, Any] = {"catalog": catalog_list}
    path.write_bytes(tomli_w.dumps(data).encode())


# ---------------------------------------------------------------------------
# Pointer-name helper
# ---------------------------------------------------------------------------


def pointer_name(name: str | None, source: str) -> str:
    """Resolve an explicit name or derive one from the source/file basename.

    Rule (documented): explicit ``name`` wins; otherwise take the last
    path component of ``source``, lowercase it, replace every non-alphanumeric
    run with ``-``, and strip leading/trailing ``-``.
    """
    if name:
        return name
    # Use the last component of the locator (after the last / or \).
    # Strip common .git suffix.
    basename = source.rstrip("/").rstrip("\\").rsplit("/", 1)[-1]
    basename = basename.rsplit("\\", 1)[-1]
    if basename.endswith(".git"):
        basename = basename[:-4]
    # Lowercase + non-alnum → '-' + trim.
    sanitized = re.sub(r"[^a-z0-9]+", "-", basename.lower()).strip("-")
    return sanitized or "catalog"


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def _find_or_create_pointer(model: CatalogModel, name: str) -> CatalogPointer:
    """Return the pointer with ``name``, creating it if absent."""
    for ptr in model.pointers:
        if ptr.name == name:
            return ptr
    ptr = CatalogPointer(name=name)
    model.pointers.append(ptr)
    return ptr


def add_source(path: Path, source: str, name: str | None = None) -> bool:
    """Add ``source`` (with optional ``@ref``) to catalog pointer ``name``.

    Creates the file if absent.  Idempotent: a source already present is a
    no-op (returns ``False``); otherwise adds and returns ``True``.  Preserves
    all other pointers and sources.

    The ``name`` defaults to a sanitized basename of ``source`` (same rule as
    :func:`pointer_name`).
    """
    model = load(path)
    src = _parse_source_string(source)
    resolved_name = pointer_name(name, src.locator)
    ptr = _find_or_create_pointer(model, resolved_name)

    # Idempotency: compare by locator (ref changes are not a no-op).
    for existing in ptr.sources:
        if existing.locator == src.locator and existing.ref == src.ref:
            return False

    ptr.sources.append(src)
    save(path, model)
    return True


def remove_source(path: Path, source: str, name: str | None = None) -> bool:
    """Remove ``source`` from catalog pointer ``name``.

    Idempotent: absent source is a no-op (returns ``False``).  Preserves all
    other pointers and sources.
    """
    model = load(path)
    src = _parse_source_string(source)
    resolved_name = pointer_name(name, src.locator)

    for ptr in model.pointers:
        if ptr.name == resolved_name:
            before = len(ptr.sources)
            ptr.sources = [
                s for s in ptr.sources if not (s.locator == src.locator and s.ref == src.ref)
            ]
            if len(ptr.sources) < before:
                save(path, model)
                return True
    return False


def list_sources(path: Path) -> CatalogModel:
    """Return the in-memory model for display; missing file → empty model."""
    return load(path)


def init_catalog(path: Path, name: str = "default") -> bool:
    """Create the catalog file with an empty pointer ``name`` if absent.

    Idempotent: existing file is left untouched (returns ``False``).
    Returns ``True`` if the file was created.
    """
    if path.is_file():
        return False
    model = CatalogModel(pointers=[CatalogPointer(name=name)])
    save(path, model)
    return True


# ---------------------------------------------------------------------------
# Deterministic listing
# ---------------------------------------------------------------------------


def _repo_basename(locator: str) -> str:
    """Derive the template name from the source locator (repo basename)."""
    base = locator.rstrip("/").rsplit("/", 1)[-1]
    if base.endswith(".git"):
        base = base[:-4]
    return base


@dataclass
class TemplateRecord:
    """A usable template entry in the listing."""

    full_id: str
    source: str  # normalized/expanded source used for discovery
    ref: str
    versions: list[str]
    reproducible: bool
    has_tasks: bool
    questions: list[str]  # visible-question key list (summary; use discover for full detail)


@dataclass
class UnusableRecord:
    """A source that could not be listed (reason explains why)."""

    source: str
    reason: str


@dataclass
class CatalogListing:
    """The deterministic listing for one catalog pointer."""

    name: str
    templates: list[TemplateRecord]
    unusable: list[UnusableRecord]


@dataclass
class FullListing:
    """The full listing across all catalog pointers."""

    catalogs: list[CatalogListing]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict matching contracts/catalog.md shape."""
        return {
            "catalogs": [
                {
                    "name": cl.name,
                    "templates": [
                        {
                            "full_id": t.full_id,
                            "source": t.source,
                            "ref": t.ref,
                            "versions": t.versions,
                            "reproducible": t.reproducible,
                            "has_tasks": t.has_tasks,
                            "questions": t.questions,
                        }
                        for t in cl.templates
                    ],
                    "unusable": [{"source": u.source, "reason": u.reason} for u in cl.unusable],
                }
                for cl in self.catalogs
            ]
        }


def build_listing(path: Path) -> FullListing:
    """Derive the deterministic template listing from all sources in the catalog.

    For each pointer (in file order), for each source, calls
    ``discovery.discover(source, ref)``.  A source that raises
    ``DiscoveryError`` OR has ``reproducible=False`` is placed in ``unusable``
    with the reason — it MUST NOT abort the whole listing (FR-005).

    Ordering is stable (deterministic):
    - Pointers: file order.
    - Templates within a pointer: sorted by ``full_id``.
    - Versions: oldest→newest (as ``list_versions`` already returns).
    No timestamps or temp-path fragments appear in the output.
    """
    model = load(path)
    catalogs: list[CatalogListing] = []

    for ptr in model.pointers:
        templates: list[TemplateRecord] = []
        unusable: list[UnusableRecord] = []

        for src in ptr.sources:
            raw_source = _source_to_string(src)
            try:
                disc = discovery.discover(src.locator, src.ref)
            except DiscoveryError as exc:
                unusable.append(UnusableRecord(source=raw_source, reason=str(exc)))
                continue

            if not disc.reproducible:
                unusable.append(
                    UnusableRecord(
                        source=raw_source,
                        reason=(
                            "not reproducible: template does not ship an answers-file "
                            ".jinja (Constitution VI)"
                        ),
                    )
                )
                continue

            template_name = _repo_basename(src.locator)
            full_id = f"{ptr.name}/{template_name}"
            question_keys = [q.key for q in disc.questions]

            templates.append(
                TemplateRecord(
                    full_id=full_id,
                    source=disc.source,
                    ref=disc.ref,
                    versions=disc.versions,
                    reproducible=disc.reproducible,
                    has_tasks=disc.has_tasks,
                    questions=question_keys,
                )
            )

        # Stable sort by full_id within each pointer.
        templates.sort(key=lambda t: t.full_id)
        catalogs.append(CatalogListing(name=ptr.name, templates=templates, unusable=unusable))

    return FullListing(catalogs=catalogs)


# ---------------------------------------------------------------------------
# Selection-validation gate
# ---------------------------------------------------------------------------


def validate_selection(path: Path, full_ids: list[str]) -> list[TemplateRecord]:
    """Validate that every requested ``full_id`` names a usable template.

    Accepts:
    - ``<catalog>/<template>`` full-ids present in the usable listing.
    - A bare ``<template>`` name that uniquely matches exactly one usable
      template across all catalogs (documented convenience — unambiguous only).

    Refuses (raises ``CatalogError``):
    - Any id not found in the usable listing.
    - A bare name that matches >1 usable template (ambiguous; full-id required).
    - A full-id that exists but is in ``unusable`` (can't select what can't be used).

    Returns the resolved ``TemplateRecord`` list for accepted ids, in the same
    order as the input ``full_ids``.
    """
    listing = build_listing(path)

    # Build lookup maps.
    usable_by_full_id: dict[str, TemplateRecord] = {}
    usable_by_short: dict[str, list[TemplateRecord]] = {}
    unusable_full_ids: set[str] = set()

    for cl in listing.catalogs:
        for t in cl.templates:
            usable_by_full_id[t.full_id] = t
            short = t.full_id.split("/", 1)[-1]
            usable_by_short.setdefault(short, []).append(t)
        for u in cl.unusable:
            # Reconstruct the full_id for unusable sources so we can give a
            # specific error when the user asks for something that is known but
            # not usable.
            source_basename = _repo_basename(u.source.split("@")[0])
            unusable_full_ids.add(f"{cl.name}/{source_basename}")

    valid_ids = sorted(usable_by_full_id.keys())

    resolved: list[TemplateRecord] = []
    for fid in full_ids:
        if fid in usable_by_full_id:
            resolved.append(usable_by_full_id[fid])
            continue

        # Check if it is a known unusable full-id.
        if fid in unusable_full_ids:
            raise CatalogError(
                f"template {fid!r} is known but not usable (see catalog list for reason). "
                f"Valid ids: {', '.join(valid_ids) or '(none)'}"
            )

        # Try bare-name resolution.
        if "/" not in fid:
            matches = usable_by_short.get(fid, [])
            if len(matches) == 1:
                resolved.append(matches[0])
                continue
            if len(matches) > 1:
                ambiguous = sorted(t.full_id for t in matches)
                raise CatalogError(
                    f"bare name {fid!r} is ambiguous — it exists under multiple catalogs: "
                    f"{', '.join(ambiguous)}. Use the full-id."
                )

        raise CatalogError(
            f"unknown template id {fid!r}. Valid ids: {', '.join(valid_ids) or '(none)'}"
        )

    return resolved
