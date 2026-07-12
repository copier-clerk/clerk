#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["copier>=9.16,<10", "pyyaml", "packaging", "tomli-w"]
# ///
"""Bundled orchestration script — the single deterministic entrypoint for the clerk skill.

Drives the full lifecycle — ``discover``, ``trust``, ``init``, ``reproduce`` — through
ONE uniform 1..N path. A single-template project is simply the N=1 case: ``reproduce``
enumerates the committed ``.copier-answers*.yml`` file(s) and drives
``copier recopy --vcs-ref=:current:`` per layer; at N=1 that is one file → one recopy.
There is no separate single-template code path and no verb meaningful only for multiple
templates.

Run via::

    ./scripts/clerk.py <verb> …          # shebang, deps importable in env
    uv run scripts/clerk.py <verb> …     # uv with the project's locked deps

Errors are printed legibly to stderr with a non-zero exit — never a bare stack trace.

Exit codes
----------
0  success
1  ClerkError (bad run-spec, copier failure, unreproducible template)
2  argparse usage error / unknown verb
3  UntrustedSourceError — source takes actions and is not trusted
4  preflight failure — a required dep is missing or version-incompatible
"""

from __future__ import annotations

import argparse

# ---------------------------------------------------------------------------
# Module-resolution shim — DUAL-MODE (BLOCKER-1 fix)
#
# When installed via APM, the package layout places a vendored `clerk/` package
# directory BESIDE `scripts/clerk.py` (i.e. scripts/clerk/ exists).  In that
# case we keep the script's own dir (`scripts/`) on sys.path so that
# `import clerk` resolves to the vendored package — no ../src needed.
#
# When running from the clerk repo itself (development), there is no sibling
# `clerk/` directory; we fall back to inserting `../src` so that
# `import clerk` resolves to `src/clerk/`.
#
# The old unconditional remove+add of ../src broke installed trees completely.
# ---------------------------------------------------------------------------
import contextlib
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent  # …/scripts  (or install_dir/scripts)
_vendored_pkg = _here / "clerk"  # sibling clerk/ package (installed case)
_src = str(_here.parent / "src")  # ../src (repo case)

if _vendored_pkg.is_dir():
    # Installed: keep script dir on path so `import clerk` finds the vendored pkg.
    # Remove ../src if it somehow crept in (shouldn't happen, but be explicit).
    with contextlib.suppress(ValueError):
        sys.path.remove(_src)
    if str(_here) not in sys.path:
        sys.path.insert(0, str(_here))
else:
    # Repo: remove scripts/ (Python inserts it for __main__ scripts) and add src/.
    with contextlib.suppress(ValueError):
        sys.path.remove(str(_here))
    if _src not in sys.path:
        sys.path.insert(0, _src)

# ---------------------------------------------------------------------------
# Preflight — runs BEFORE third-party imports so --help and `doctor` work
# even when deps are absent.  Third-party imports are deferred to after the
# preflight passes (or the `doctor` verb is dispatched).
# ---------------------------------------------------------------------------
# _preflight itself is stdlib-only; it is part of clerk's vendored package so
# it is importable immediately after the shim above.
from clerk._preflight import missing_or_incompatible, report  # noqa: E402


def _run_preflight_or_exit() -> None:
    """Check deps; print a suggestion and exit 4 if any are missing/incompatible."""
    issues = missing_or_incompatible()
    if issues:
        print(report(issues), file=sys.stderr)
        raise SystemExit(4)


# ---------------------------------------------------------------------------
# Parser — built BEFORE preflight so --help / doctor work without deps.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clerk.py",
        description=(
            "Bundled copier conductor — discovers templates, manages trust, "
            "inits and reproduces projects through one uniform 1..N path."
        ),
    )
    from clerk import (
        __version__,  # noqa: PLC0415 — clerk.__init__ is stdlib-only, safe pre-preflight
    )

    parser.add_argument("-V", "--version", action="version", version=f"clerk {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_discover = sub.add_parser("discover", help="Inspect one template (static, JSON out).")
    p_discover.add_argument(
        "source", help="Fetchable template source (expanded https URL or path)."
    )
    p_discover.add_argument("--ref", default=None, help="Pin to a specific version/ref.")
    p_discover.set_defaults(func=_deferred_dispatch)

    p_init = sub.add_parser("init", help="Generate a project from a frozen run-spec.")
    p_init.add_argument(
        "--run-spec", required=True, help="Path to the inputs document (JSON/YAML)."
    )
    p_init.add_argument("--check", action="store_true", help="Dry-run validate; write nothing.")
    p_init.set_defaults(func=_deferred_dispatch)

    p_repro = sub.add_parser("reproduce", help="Faithfully reproduce an existing project.")
    p_repro.add_argument("dest", nargs="?", default=".", help="Project directory (default: cwd).")
    p_repro.set_defaults(func=_deferred_dispatch)

    p_catalog = sub.add_parser("catalog", help="Manage the user-owned source catalog.")
    p_catalog.add_argument(
        "--catalog",
        metavar="PATH",
        default=None,
        help="Override the catalog file path (default: CLERK_CATALOG_PATH or platformdirs).",
    )
    catalog_sub = p_catalog.add_subparsers(dest="catalog_cmd", required=True)

    p_cat_init = catalog_sub.add_parser(
        "init", help="Create the catalog file if absent (idempotent)."
    )
    p_cat_init.add_argument("--name", default=None, help="Name for the initial catalog pointer.")
    p_cat_init.set_defaults(func=_deferred_dispatch)

    p_cat_add = catalog_sub.add_parser("add", help="Add a source to the catalog.")
    p_cat_add.add_argument("source", help="Source locator (gituser/gitrepo or URL, optional @ref).")
    p_cat_add.add_argument(
        "--name", default=None, help="Catalog pointer name (default: sanitized source basename)."
    )
    p_cat_add.set_defaults(func=_deferred_dispatch)

    p_cat_remove = catalog_sub.add_parser("remove", help="Remove a source from the catalog.")
    p_cat_remove.add_argument("source", help="Source locator to remove.")
    p_cat_remove.add_argument(
        "--name", default=None, help="Catalog pointer name (default: sanitized source basename)."
    )
    p_cat_remove.set_defaults(func=_deferred_dispatch)

    p_cat_list = catalog_sub.add_parser(
        "list", help="List all templates (static discovery, deterministic)."
    )
    p_cat_list.add_argument(
        "--json", action="store_true", dest="json", help="Emit machine-readable JSON."
    )
    p_cat_list.set_defaults(func=_deferred_dispatch)

    p_cat_refresh = catalog_sub.add_parser(
        "refresh",
        help="Re-discover all sources (same as list; explicit freshness trigger).",
    )
    p_cat_refresh.add_argument(
        "--json", action="store_true", dest="json", help="Emit machine-readable JSON."
    )
    p_cat_refresh.set_defaults(func=_deferred_dispatch)

    p_cat_validate = catalog_sub.add_parser(
        "validate", help="Validate one or more full-ids against the discovered catalog."
    )
    p_cat_validate.add_argument("full_ids", nargs="+", metavar="full-id", help="Full template ids.")
    p_cat_validate.set_defaults(func=_deferred_dispatch)

    p_trust = sub.add_parser("trust", help="Manage trusted template sources.")
    trust_sub = p_trust.add_subparsers(dest="trust_cmd", required=True)

    p_trust_add = trust_sub.add_parser("add", help="Record a trusted source prefix (on consent).")
    _trust_add_group = p_trust_add.add_mutually_exclusive_group(required=True)
    _trust_add_group.add_argument(
        "prefix",
        nargs="?",
        default=None,
        help="Fully-expanded https prefix or exact URL to trust.",
    )
    _trust_add_group.add_argument(
        "--from-source",
        metavar="SRC",
        default=None,
        help="Compute and record the owner-path prefix for SRC.",
    )
    p_trust_add.set_defaults(func=_deferred_dispatch)

    p_trust_list = trust_sub.add_parser("list", help="List trusted sources.")
    p_trust_list.set_defaults(func=_deferred_dispatch)

    p_update = sub.add_parser(
        "update",
        help=(
            "Upgrade a project to a newer template version (spec 006). "
            "Requires a clean git working tree (commit or stash changes first)."
        ),
        description=(
            "Upgrade a project to a newer template version (spec 006). "
            "Requires a clean git working tree: upgrade commits each template layer "
            "between layers, and copier refuses a dirty tree even with --pretend. "
            "Commit or stash your changes first."
        ),
    )
    p_update.add_argument("dest", nargs="?", default=".", help="Project directory (default: cwd).")
    p_update.add_argument(
        "--vcs-ref",
        default=None,
        dest="vcs_ref",
        help="Target version tag (default: latest PEP 440 tag per layer).",
    )
    p_update.add_argument(
        "--pretend",
        action="store_true",
        help="Dry-run: preview what would change without writing.",
    )
    p_update.add_argument(
        "--conflict",
        choices=["inline", "rej"],
        default="inline",
        help="Conflict mode: 'inline' (default) writes markers; 'rej' writes .rej files.",
    )
    p_update.add_argument(
        "--skip-tasks",
        action="store_true",
        dest="skip_tasks",
        help=(
            "Suppress _tasks during update. "
            "NOTE: does NOT suppress _migrations (copier limitation; see spec 006)."
        ),
    )
    p_update.set_defaults(func=_deferred_dispatch)

    p_doctor = sub.add_parser(
        "doctor",
        help="Check that all required deps are installed and version-compatible.",
    )
    p_doctor.set_defaults(func=_cmd_doctor)

    return parser


# ---------------------------------------------------------------------------
# Doctor verb (runs without third-party deps — preflight is stdlib-only)
# ---------------------------------------------------------------------------


def _cmd_doctor(_args: argparse.Namespace) -> int:
    """Report on dep readiness; exit 0 if all present+compatible, 4 otherwise."""
    issues = missing_or_incompatible()
    if not issues:
        print("clerk: all dependencies present and version-compatible. Ready.")
        return 0
    print(report(issues), file=sys.stderr)
    return 4


# ---------------------------------------------------------------------------
# Deferred dispatch — resolved after preflight passes
# ---------------------------------------------------------------------------

# These handlers import third-party modules lazily (after the preflight gate).
# They are registered as `func` on every non-doctor subparser; the dispatcher
# below calls _run_preflight_or_exit() first, then re-dispatches to the real
# implementation.


def _deferred_dispatch(args: argparse.Namespace) -> int:  # noqa: PLR0911
    """Gate on preflight, then import third-party modules and dispatch."""
    _run_preflight_or_exit()
    return _real_dispatch(args)


def _real_dispatch(args: argparse.Namespace) -> int:  # noqa: PLR0911
    """Dispatch after preflight has confirmed deps are available."""
    # Third-party imports happen here — safe because preflight passed.
    import json
    from datetime import date

    import yaml

    from clerk import catalog, discovery, runner, trust
    from clerk.catalog import TemplateRecord
    from clerk.errors import ClerkError, InvalidRunSpecError, UntrustedSourceError

    # --- helpers (re-declared inside to avoid top-level third-party deps) ---

    def _today() -> str:
        return date.today().isoformat()  # noqa: DTZ011

    def _load_run_spec(path: str) -> runner.RunSpec:
        raw = Path(path).read_text()
        data = yaml.safe_load(raw)
        return runner.RunSpec.from_mapping(data)

    def _load_multi_run_spec(
        path: str,
    ) -> tuple[str, list[tuple[TemplateRecord, dict[str, object]]]]:
        raw = Path(path).read_text()
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise InvalidRunSpecError("multi run-spec must be a mapping")
        dest = data.get("dest")
        if not dest:
            raise InvalidRunSpecError("multi run-spec missing required field: dest")
        selection_raw = data.get("selection")
        if not isinstance(selection_raw, list) or not selection_raw:
            raise InvalidRunSpecError("multi run-spec 'selection' must be a non-empty list")
        result: list[tuple[TemplateRecord, dict[str, object]]] = []
        for i, entry in enumerate(selection_raw):
            if not isinstance(entry, dict):
                raise InvalidRunSpecError(f"selection[{i}] must be a mapping")
            full_id = entry.get("full_id")
            source = entry.get("source")
            if not full_id:
                raise InvalidRunSpecError(f"selection[{i}] missing 'full_id'")
            if not source:
                raise InvalidRunSpecError(f"selection[{i}] missing 'source'")
            ref = entry.get("ref") or None
            answers = entry.get("answers") or {}
            if not isinstance(answers, dict):
                raise InvalidRunSpecError(f"selection[{i}] 'answers' must be a mapping")
            record = TemplateRecord(
                full_id=str(full_id),
                source=str(source),
                ref=str(ref) if ref else "",
                versions=[],
                reproducible=True,
                has_tasks=False,
                questions=[],
            )
            result.append((record, dict(answers)))
        return str(dest), result

    def _is_multi_run_spec(path: str) -> bool:
        try:
            raw = Path(path).read_text()
            data = yaml.safe_load(raw)
            return isinstance(data, dict) and "selection" in data
        except Exception:  # noqa: BLE001
            return False

    # --- verb implementations ---

    def _cmd_discover(a: argparse.Namespace) -> int:
        desc = discovery.discover(a.source, a.ref)
        print(json.dumps(desc.to_dict(), indent=2))
        return 0

    def _cmd_init(a: argparse.Namespace) -> int:
        if _is_multi_run_spec(a.run_spec):
            dest, selection = _load_multi_run_spec(a.run_spec)
            results = runner.init_many(selection, dest, today=_today(), check=a.check)
            if results and results[0].pretend:
                layer_ids = ", ".join(r.src for r in results)
                print(
                    f"OK: inputs valid for {len(results)} layer(s)"
                    f" [{layer_ids}] (no files written)."
                )
            else:
                print(f"OK: generated {dest} from {len(results)} layer(s).")
        else:
            spec = _load_run_spec(a.run_spec)
            result = runner.init(spec, today=_today(), check=a.check)
            if result.pretend:
                print(f"OK: inputs valid for {spec.source} (no files written).")
            else:
                print(f"OK: generated {spec.dest} from {spec.source}.")
        return 0

    def _cmd_reproduce(a: argparse.Namespace) -> int:
        dest = a.dest
        try:
            runner.reproduce_many(dest)
        except ClerkError:
            raise
        print(f"OK: reproduced {dest} faithfully at its recorded commit.")
        return 0

    def _cmd_catalog(a: argparse.Namespace) -> int:  # noqa: PLR0911
        cat_path = Path(a.catalog) if a.catalog else catalog.catalog_path()
        verb = a.catalog_cmd

        if verb == "init":
            name: str = a.name or "default"
            created = catalog.init_catalog(cat_path, name=name)
            if created:
                print(f"created: {cat_path}")
            else:
                print(f"notice: catalog already exists (untouched): {cat_path}")
            return 0

        if verb == "add":
            added = catalog.add_source(cat_path, a.source, name=a.name)
            if added:
                print(f"added: {a.source}")
            else:
                print(f"already present (no-op): {a.source}")
            return 0

        if verb == "remove":
            removed = catalog.remove_source(cat_path, a.source, name=a.name)
            if removed:
                print(f"removed: {a.source}")
            else:
                print(f"not found (no-op): {a.source}")
            return 0

        if verb in ("list", "refresh"):
            if not cat_path.is_file():
                print(
                    f"error: no catalog at {cat_path!r}. "
                    f"Run 'catalog init' or 'catalog add <source>' first.",
                    file=sys.stderr,
                )
                return 1
            listing = catalog.build_listing(cat_path)
            if getattr(a, "json", False):
                print(json.dumps(listing.to_dict(), indent=2))
            else:
                _print_catalog_table(listing)
            return 0

        if verb == "validate":
            if not cat_path.is_file():
                print(
                    f"error: no catalog at {cat_path!r}. "
                    f"Run 'catalog init' or 'catalog add <source>' first.",
                    file=sys.stderr,
                )
                return 1
            records = catalog.validate_selection(cat_path, list(a.full_ids))
            for rec in records:
                print(f"ok: {rec.full_id} ({rec.source} @ {rec.ref})")
            return 0

        return 2

    def _print_catalog_table(listing: catalog.FullListing) -> None:
        if not listing.catalogs:
            print("(empty catalog)")
            return
        for cl in listing.catalogs:
            print(f"catalog: {cl.name}")
            if cl.templates:
                for t in cl.templates:
                    versions_str = ", ".join(t.versions[-3:])
                    if len(t.versions) > 3:
                        versions_str = f"… {versions_str}"
                    tasks_flag = " [tasks]" if t.has_tasks else ""
                    print(f"  {t.full_id}{tasks_flag}")
                    print(f"    source:    {t.source}")
                    print(f"    ref:       {t.ref}")
                    print(f"    versions:  {versions_str}")
                    print(f"    questions: {', '.join(t.questions) or '(none)'}")
            else:
                print("  (no usable templates)")
            if cl.unusable:
                print("  unusable:")
                for u in cl.unusable:
                    print(f"    - {u.source}: {u.reason}")

    def _cmd_trust(a: argparse.Namespace) -> int:
        if a.trust_cmd == "add":
            prefix = trust.suggest_prefix(a.from_source) if a.from_source else a.prefix
            added = trust.add_trust(prefix)
            print(f"{'added' if added else 'already trusted'}: {prefix}")
            return 0
        if a.trust_cmd == "list":
            entries = trust.list_trust()
            if entries:
                print("\n".join(entries))
            else:
                print("(no trusted sources)")
            return 0
        return 2

    def _cmd_update(a: argparse.Namespace) -> int:
        dest = a.dest
        results = runner.update_many(
            dest,
            vcs_ref=a.vcs_ref or None,
            pretend=a.pretend,
            conflict=a.conflict,
            skip_tasks=a.skip_tasks,
        )
        if results and results[0].pretend:
            print(f"OK: dry-run upgrade preview for {len(results)} layer(s) (no files written).")
        else:
            print(f"OK: upgraded {dest} ({len(results)} layer(s)).")
        return 0

    # --- dispatch table ---
    cmd = args.command
    try:
        if cmd == "discover":
            return _cmd_discover(args)
        if cmd == "init":
            return _cmd_init(args)
        if cmd == "reproduce":
            return _cmd_reproduce(args)
        if cmd == "catalog":
            return _cmd_catalog(args)
        if cmd == "trust":
            return _cmd_trust(args)
        if cmd == "update":
            return _cmd_update(args)
    except UntrustedSourceError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ClerkError as exc:
        # MergeConflictError subclasses ClerkError — exit 4 so callers can distinguish
        # "conflicts to resolve" from hard errors (exit 1).
        from clerk.errors import MergeConflictError

        if isinstance(exc, MergeConflictError):
            print(f"error: {exc}", file=sys.stderr)
            return 4
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 2


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Dispatch a clerk verb from ``argv`` (or ``sys.argv[1:]``)."""
    args_list = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    ns = parser.parse_args(args_list)

    if not getattr(ns, "command", None):
        parser.print_help()
        return 0

    func = getattr(ns, "func", None)
    if func is None:
        parser.print_help()
        return 0

    return int(func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
