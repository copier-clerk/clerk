#!/usr/bin/env python3
"""Commit-message hook: enforce Conventional Commits format.

Validates that the commit subject matches:
  <type>[optional scope]: <description>

Allowed types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert

Exits 0 on valid, 1 on violation (pre-commit interprets non-zero as failure).
"""

from __future__ import annotations

import re
import sys

# Conventional Commits type allowlist.
_TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)

_PATTERN = re.compile(
    r"^(?P<type>" + "|".join(_TYPES) + r")"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<desc>.+)$",
    re.MULTILINE,
)


def main(argv: list[str] = sys.argv) -> int:
    if len(argv) < 2:
        print("usage: check-commit-msg.py <commit-msg-file>", file=sys.stderr)
        return 2

    msg_path = argv[1]
    try:
        with open(msg_path) as fh:
            msg = fh.read()
    except OSError as exc:
        print(f"check-commit-msg: cannot read {msg_path}: {exc}", file=sys.stderr)
        return 2

    # Extract subject line (first non-empty, non-comment line).
    subject = next(
        (line for line in msg.splitlines() if line and not line.startswith("#")),
        "",
    )

    if _PATTERN.match(subject):
        return 0

    print(
        f"check-commit-msg: FAIL — subject does not match Conventional Commits.\n"
        f"  Subject: {subject!r}\n"
        f"  Expected: <type>[(<scope>)][!]: <description>\n"
        f"  Types:    {', '.join(_TYPES)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
