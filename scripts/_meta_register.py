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

    The skeleton demonstrates the spec 014 model:
    - _external_data alias for base facts (always-present producer)
    - depends_on edge as a hidden when:false answer
    - _bailiff_phase declaration
    - Fragment contribution placeholders for .mise/conf.d/, .pre-commit.d/, .gitignore.d/
    """
    dst = Path("templates") / name / "copier.yml"
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# copier.yml — {name}\n"
        "#\n"
        "# Outputs (spec 014 fragment/merge model):\n"
        f"#   MANAGED: .mise/conf.d/{name}.toml,\n"
        f"#            .pre-commit.d/{name}.yaml,\n"
        f"#            .gitignore.d/{name}\n"
        "#   SEED-ONCE: <TODO: list any _skip_if_exists files>\n"
        "#   TASK-OUTPUT: <TODO: list any native-init files>\n"
        "#\n"
        "# Answers-file key — MUST match the shipped .jinja file (FR-016).\n"
        # Not an f-string — literal {{ }} needed for the YAML value
        '_answers_file: "{{ _copier_conf.answers_file }}.jinja"\n'
        "\n"
        "# --- External data aliases (spec 014 FR-004) ---------------------------------\n"
        "# Reads facts from base (always present). Each alias is a hard dependency:\n"
        "# base absent from selection → preflight OrderingError (R6).\n"
        "_external_data:\n"
        "  base: .copier-answers.bailiff-mod-base.yml\n"
        "\n"
        "# --- Facts read from base ----------------------------------------------------\n"
        "\n"
        "project_name:\n"
        "  type: str\n"
        "  default: \"{{ _external_data.base.project_name | default('', true) }}\"\n"
        '  help: "Project name (from bailiff-mod-base via _external_data; standalone: empty)."\n'
        "\n"
        "# --- Questions ---------------------------------------------------------------\n"
        "# Add module-specific questions here.\n"
        "\n"
        "# --- Dependency ordering (spec 014 R7/R8) ------------------------------------\n"
        "# phase: normal (base=pre, all other modules=normal; post is reserved).\n"
        "_bailiff_phase: normal\n"
        "\n"
        "# depends_on declares ordering + presence requirements (R6/R7).\n"
        "# A dangling edge (target absent from selection) is a preflight OrderingError.\n"
        "depends_on:\n"
        "  type: yaml\n"
        "  default:\n"
        "    - bailiff-mod-base\n"
        "  when: false\n"
        "\n"
        "# Template body lives under template/ — copier renders only that subtree.\n"
        "_subdirectory: template\n"
        "\n"
        "# --- Trust-gated tasks -------------------------------------------------------\n"
        "# Tasks run post-render at BOTH init and reproduce.\n"
        "# Init-only guard (FR-012a): use `test -f <sentinel> || <command>` to prevent\n"
        "# re-running expensive steps on reproduce over a populated tree.\n"
        "_tasks: []\n"
        "\n"
        "# --- Post-tasks (deferred work after the full render loop, spec 014 R11) ------\n"
        "# Declare here only if this module owns a merged-output file (e.g. the\n"
        "# pre-commit bundler or the gitignore concat). Most modules leave this empty.\n"
        "# _post_tasks: []\n"
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
