#!/usr/bin/env python3
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
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import date
from pathlib import Path

# When run directly (./scripts/clerk.py or python scripts/clerk.py), Python inserts the
# script's own directory at sys.path[0], which makes `import clerk` resolve to this
# file instead of src/clerk. Remove scripts/ and ensure src/ is searched first.
_here = Path(__file__).resolve().parent  # …/scripts
_src = str(_here.parent / "src")
with contextlib.suppress(ValueError):
    sys.path.remove(str(_here))
if _src not in sys.path:
    sys.path.insert(0, _src)

import yaml  # noqa: E402

from clerk import __version__, discovery, runner, trust  # noqa: E402
from clerk.errors import ClerkError, UntrustedSourceError  # noqa: E402


def _today() -> str:
    """clerk's own clock, injected as the frozen ``today`` answer."""
    return date.today().isoformat()  # noqa: DTZ011 — a calendar date is intended


def _load_run_spec(path: str) -> runner.RunSpec:
    raw = Path(path).read_text()
    data = yaml.safe_load(raw)  # JSON is valid YAML, so this accepts both
    return runner.RunSpec.from_mapping(data)


# ---------------------------------------------------------------------------
# Verb handlers
# ---------------------------------------------------------------------------


def _cmd_discover(args: argparse.Namespace) -> int:
    desc = discovery.discover(args.source, args.ref)
    print(json.dumps(desc.to_dict(), indent=2))
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    spec = _load_run_spec(args.run_spec)
    result = runner.init(spec, today=_today(), check=args.check)
    if result.pretend:
        print(f"OK: inputs valid for {spec.source} (no files written).")
    else:
        print(f"OK: generated {spec.dest} from {spec.source}.")
    return 0


def _cmd_reproduce(args: argparse.Namespace) -> int:
    dest = args.dest
    answers_files = runner.enumerate_answers_files(dest)
    if not answers_files:
        print(
            f"error: no .copier-answers*.yml at {dest!r}; nothing to reproduce",
            file=sys.stderr,
        )
        return 1
    for answers_file in answers_files:
        runner.reproduce(dest, answers_file=answers_file)
    print(f"OK: reproduced {dest} faithfully at its recorded commit.")
    return 0


def _cmd_trust(args: argparse.Namespace) -> int:
    if args.trust_cmd == "add":
        prefix = trust.suggest_prefix(args.from_source) if args.from_source else args.prefix
        added = trust.add_trust(prefix)
        print(f"{'added' if added else 'already trusted'}: {prefix}")
        return 0
    if args.trust_cmd == "list":
        entries = trust.list_trust()
        if entries:
            print("\n".join(entries))
        else:
            print("(no trusted sources)")
        return 0
    return 2


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clerk.py",
        description=(
            "Bundled copier conductor — discovers templates, manages trust, "
            "inits and reproduces projects through one uniform 1..N path."
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=f"clerk {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_discover = sub.add_parser("discover", help="Inspect one template (static, JSON out).")
    p_discover.add_argument(
        "source", help="Fetchable template source (expanded https URL or path)."
    )
    p_discover.add_argument("--ref", default=None, help="Pin to a specific version/ref.")
    p_discover.set_defaults(func=_cmd_discover)

    p_init = sub.add_parser("init", help="Generate a project from a frozen run-spec.")
    p_init.add_argument(
        "--run-spec", required=True, help="Path to the inputs document (JSON/YAML)."
    )
    p_init.add_argument("--check", action="store_true", help="Dry-run validate; write nothing.")
    p_init.set_defaults(func=_cmd_init)

    p_repro = sub.add_parser("reproduce", help="Faithfully reproduce an existing project.")
    p_repro.add_argument("dest", nargs="?", default=".", help="Project directory (default: cwd).")
    p_repro.set_defaults(func=_cmd_reproduce)

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
    p_trust_add.set_defaults(func=_cmd_trust)

    p_trust_list = trust_sub.add_parser("list", help="List trusted sources.")
    p_trust_list.set_defaults(func=_cmd_trust)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Dispatch a clerk verb from ``argv`` (or ``sys.argv[1:]``)."""
    args = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    ns = parser.parse_args(args)
    if not getattr(ns, "command", None):
        parser.print_help()
        return 0
    try:
        return int(ns.func(ns))
    except UntrustedSourceError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except ClerkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
