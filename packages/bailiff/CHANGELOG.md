# Changelog

## 0.1.0 (2026-07-12)

Initial release — bailiff skill installable via Claude Code and Codex APM marketplaces.

- Bundled `scripts/bailiff.py` entrypoint (discover / trust / init / reproduce / doctor).
- Vendored `src/bailiff/` modules (no PyPI `bailiff` package required).
- Dep preflight: checks `copier>=9.16,<10`, `pyyaml`, `packaging`, `tomli-w`;
  environment-aware install suggestion (uv/pipx/pip; brew only for copier).
- `bailiff doctor` verb: explicit readiness report (exit 0 = ready, 4 = issues).
- PEP 723 header for frictionless `uv run scripts/bailiff.py` usage.
