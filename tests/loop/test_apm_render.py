"""spec 007 US1 / SC-001, SC-006, Q2, Q4 (T011): bailiff-mod-apm renders correctly.

Render bailiff-mod-apm and assert:
- an injected apm_packages set produces an apm.yml with exactly those
  dependencies.apm[] entries plus >= 1 inline source (SC-001, Q2 / FR-002a);
- the injected list persists to the recorded answers (Q2 / FR-008);
- rendered standalone (no base) it falls back to a default project_name (SC-006);
- an empty apm_packages set is REFUSED (Q4 / FR-002b) with no apm.yml written.

The install task is the offline stub (bailiff_mod_apm fixture); a real apm install
is out of the hermetic set.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bailiff import runner, trust
from bailiff.errors import InvalidRunSpecError
from tests.conftest import TemplateRepo

_PKGS = [
    "srobroek/agentic-packages/packages/speckit#>=5.0.0 <6.0.0",
    "srobroek/agentic-packages/packages/dep-audit#>=1.0.0 <2.0.0",
]


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(tmp_path / "settings.yml"))


def _init_apm(repo: TemplateRepo, dest: Path, answers: dict[str, object]) -> None:
    trust.add_trust(repo.url)
    spec = runner.RunSpec(source=repo.url, dest=str(dest), answers=answers)
    runner.init(spec, today="2026-07-13")


def test_apm_renders_injected_packages_and_sources(
    bailiff_mod_apm: TemplateRepo, tmp_path: Path
) -> None:
    """SC-001 / Q2: apm.yml has exactly the injected deps + >= 1 inline source."""
    dest = tmp_path / "proj"
    _init_apm(bailiff_mod_apm, dest, {"project_name": "myapp", "apm_packages": _PKGS})

    apm_yml = (dest / "apm.yml").read_text()
    parsed = yaml.safe_load(apm_yml)
    assert parsed["name"] == "myapp", "project_name not rendered into apm.yml name"
    deps = parsed["dependencies"]["apm"]
    assert deps == _PKGS, f"dependencies.apm[] mismatch: {deps}"
    # FR-002a: >= 1 catalogue/registry source. APM has no separate consumer
    # catalogue block — each locator carries its own inline source, so >= 1 dep
    # == >= 1 source. Assert every dep is a real inline source locator.
    assert len(deps) >= 1
    for d in deps:
        assert "/" in d and "#" in d, f"dependency {d!r} is not an inline source locator"

    # Q2 / FR-008: the injected list persists to the recorded answers.
    af = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    assert af["apm_packages"] == _PKGS, "apm_packages not persisted to answers file"
    assert af["_commit"], "answers file must record a pinned _commit"
    # Hidden edges are never persisted.
    assert "depends_on" not in af
    assert "run_after" not in af

    # The offline install stub ran and wrote the external-state lock.
    assert (dest / ".bailiff-apm-preflight").is_file(), "apm preflight stub did not run"
    assert (dest / "apm.lock.yaml").is_file(), "install task did not write apm.lock.yaml"


def test_apm_renders_standalone_with_default_name(
    bailiff_mod_apm: TemplateRepo, tmp_path: Path
) -> None:
    """SC-006: applied in isolation (no base), project_name falls back to a default."""
    dest = tmp_path / "proj"
    _init_apm(bailiff_mod_apm, dest, {"apm_packages": ["x/y/packages/z#>=1.0.0 <2.0.0"]})

    parsed = yaml.safe_load((dest / "apm.yml").read_text())
    # Self-contained: no upstream project_name → the default fallback renders, no crash.
    assert parsed["name"] == "project", "standalone must fall back to a default name"
    assert parsed["dependencies"]["apm"] == ["x/y/packages/z#>=1.0.0 <2.0.0"]


def test_apm_empty_set_refused_no_file(bailiff_mod_apm: TemplateRepo, tmp_path: Path) -> None:
    """Q4 / FR-002b: an empty apm_packages set is refused; no apm.yml is written."""
    dest = tmp_path / "proj"
    trust.add_trust(bailiff_mod_apm.url)
    spec = runner.RunSpec(
        source=bailiff_mod_apm.url,
        dest=str(dest),
        answers={"project_name": "myapp", "apm_packages": []},
    )
    with pytest.raises(InvalidRunSpecError) as excinfo:
        runner.init(spec, today="2026-07-13")

    # The refusal message must direct the user to drop the module (Q4).
    msg = str(excinfo.value)
    assert "at least one APM package" in msg or "drop" in msg, f"unhelpful refusal: {msg}"
    # No apm.yml written on refusal.
    assert not (dest / "apm.yml").exists() if dest.exists() else True
