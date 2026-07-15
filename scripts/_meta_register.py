#!/usr/bin/env python3
"""Post-scaffold registration helper for `just new-module` (spec 008b).

Called by the meta-template's _tasks after copier renders the module stub.
Performs four operations:
  copier_yml — creates templates/<name>/copier.yml (copier skips copier.yml.jinja)
  answers    — creates the {{ _copier_conf.answers_file }}.jinja file
  cog        — appends [monorepo.packages.<name>] to cog.toml
  catalog    — appends [[sources]] url to catalog-sources.toml

Run from the monorepo root (copier tasks always run in the destination).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _copier_yml(name: str) -> None:
    """Create templates/<name>/copier.yml skeleton.

    copier intentionally skips copier.yml.jinja files during rendering (they would
    conflict with the meta-template config), so we create the module's copier.yml here.
    """
    dst = Path("templates") / name / "copier.yml"
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# copier.yml — {name}\n"
        "#\n"
        "# Answers-file key — MUST match the shipped .jinja file (FR-016).\n"
        # Not an f-string — literal {{ }} needed for the YAML value
        '_answers_file: "{{ _copier_conf.answers_file }}.jinja"\n'
        "\n"
        "# --- Questions ---------------------------------------------------------------\n"
        "# Replace these placeholders with real questions for this module.\n"
        "\n"
        "project_name:\n"
        "  type: str\n"
        '  help: "Name of the generated project."\n'
        "\n"
        "description:\n"
        "  type: str\n"
        '  default: ""\n'
        '  help: "One-line description of the project."\n'
    )
    dst.write_text(content)
    print(f"  created {dst}")


def _answers(name: str) -> None:
    """Create the answers-file template with a literal Jinja filename."""
    dst = Path("templates") / name / "{{ _copier_conf.answers_file }}.jinja"
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        "# Managed by copier — do not edit by hand.\n{{ _copier_answers|to_nice_yaml }}\n"
    )
    print(f"  created {dst}")


def _cog(name: str) -> None:
    """Append package entry to cog.toml [monorepo.packages]."""
    cog = Path("cog.toml")
    text = cog.read_text() if cog.exists() else ""
    key = f"[monorepo.packages.{name}]"
    if key in text:
        return
    entry = f'\n[monorepo.packages.{name}]\npath = "templates/{name}"\n'
    cog.write_text(text + entry)
    print(f"  registered {name} in cog.toml")


def _catalog(name: str) -> None:
    """Append source entry to catalog-sources.toml."""
    src = Path("catalog-sources.toml")
    text = src.read_text() if src.exists() else ""
    url = f"https://github.com/bailiff-io/{name}.git"
    if url in text:
        return
    entry = f'\n[[sources]]\nurl = "{url}"\n'
    src.write_text(text + entry)
    print(f"  registered {name} in catalog-sources.toml")


if __name__ == "__main__":
    if len(sys.argv) != 3:  # noqa: PLR2004
        print(
            "Usage: _meta_register.py <copier_yml|answers|cog|catalog> <module_name>",
            file=sys.stderr,
        )
        sys.exit(2)
    op, module_name = sys.argv[1], sys.argv[2]
    if op == "copier_yml":
        _copier_yml(module_name)
    elif op == "answers":
        _answers(module_name)
    elif op == "cog":
        _cog(module_name)
    elif op == "catalog":
        _catalog(module_name)
    else:
        print(f"Unknown operation: {op}", file=sys.stderr)
        sys.exit(2)
