# Changelog

## 0.1.0 (2026-07-12)

Initial release — clerk skill installable via Claude Code and Codex APM marketplaces.

- Bundled `scripts/clerk.py` entrypoint (discover / trust / init / reproduce / doctor).
- Vendored `src/clerk/` modules (no PyPI `clerk` package required).
- Dep preflight: checks `copier>=9.16,<10`, `pyyaml`, `packaging`, `tomli-w`;
  environment-aware install suggestion (uv/pipx/pip; brew only for copier).
- `clerk doctor` verb: explicit readiness report (exit 0 = ready, 4 = issues).
- PEP 723 header for frictionless `uv run scripts/clerk.py` usage.
