"""clerk command-line entry point.

Placeholder — the real CLI is spec-driven and not yet implemented. See
docs/decisions/ for the architecture and the SpecKit workflow for delivery.
"""

from __future__ import annotations

import sys

from clerk import __version__


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``clerk`` console script."""
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("-V", "--version"):
        print(f"clerk {__version__}")
        return 0
    print("clerk: an agentic conductor for copier (not yet implemented)")
    print("See docs/decisions/ for the architecture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
