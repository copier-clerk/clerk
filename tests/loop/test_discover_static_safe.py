"""US3 / FR-004a: discovery is static and safe on untrusted sources.

The load-bearing safety property: inspecting a template MUST NOT execute any
template-authored code and MUST NOT require trust. copier's Jinja environment
imports template-declared ``_jinja_extensions`` at construction (arbitrary code,
NOT trust-gated), so discovery must never build it. Here we point discovery at a
template that declares a hostile extension whose import raises — if discovery
built the env, this would blow up; instead discovery reads copier.yml statically
and succeeds.
"""

from __future__ import annotations

from tests.conftest import build_template_repo


def test_discovery_does_not_import_declared_extensions(tmp_path) -> None:
    repo = build_template_repo(
        tmp_path / "hostile",
        files={
            # A module that detonates on import — proves no import happens.
            "boom.py": "raise RuntimeError('extension imported = code executed at discovery')\n",
            "copier.yml": (
                "_jinja_extensions:\n  - boom.Boom\n"
                "project_name:\n  type: str\n"
                "_subdirectory: template\n"
            ),
            "template/out.txt.jinja": "{{ project_name }}\n",
        },
    )

    # No trust is configured and none is passed — discovery must still succeed.
    from bailiff.discovery import discover

    d = discover(repo.url)

    # It surfaced the declared extension as data (a string), without importing it.
    assert d.jinja_extensions == ["boom.Boom"]
    assert {q.key for q in d.questions} == {"project_name"}


def test_discovery_needs_no_trust_settings(tmp_path, monkeypatch) -> None:
    # Point copier's settings path at an empty dir: even with zero trust config,
    # discovery works (it never consults trust).
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "nonexistent-settings.yml"))
    repo = build_template_repo(
        tmp_path / "tpl",
        files={
            "copier.yml": "project_name:\n  type: str\n_subdirectory: template\n",
            "template/out.txt.jinja": "{{ project_name }}\n",
        },
    )
    from bailiff.discovery import discover

    assert discover(repo.url).reproducible is True
