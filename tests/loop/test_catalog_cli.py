"""T014: subprocess-drive catalog verbs against a hermetic fixture catalog.

All invocations use ``catalog --catalog <tmp>`` (flag on the parent parser, before
the subverb) so the real user config is never touched (SC-005).  Belt-and-suspenders:
``BAILIFF_CATALOG_PATH`` is also overridden to a per-test tmp path in every subprocess
env, mirroring how the trust tests isolate via ``COPIER_SETTINGS_PATH``.

Covers: init idempotence, add/remove CRUD + idempotence, list + list --json shape
and determinism, per-source failure isolation, validate exit codes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import tomli_w

from tests.conftest import _SIMPLE_COPIER_YML, MultiSourceCatalog, build_template_repo

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bailiff.py"


def _bailiff(
    *args: str,
    catalog: Path,
    env_catalog_fallback: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run ``scripts/bailiff.py catalog --catalog <catalog> <args>``.

    Sets BAILIFF_CATALOG_PATH to ``env_catalog_fallback`` (or the same ``catalog``
    path when not given) so that even if the ``--catalog`` flag were absent the
    process would not fall through to the real user config.
    """
    fallback = env_catalog_fallback if env_catalog_fallback is not None else catalog
    full_env = {**os.environ, "BAILIFF_CATALOG_PATH": str(fallback)}
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "catalog", "--catalog", str(catalog), *args],
        capture_output=True,
        text=True,
        env=full_env,
    )


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_catalog_init_creates_file(tmp_path: Path) -> None:
    cat = tmp_path / "new" / "catalog.toml"
    r = _bailiff("init", catalog=cat)
    assert r.returncode == 0
    assert cat.is_file()


def test_catalog_init_idempotent(tmp_path: Path) -> None:
    cat = tmp_path / "catalog.toml"
    _bailiff("init", catalog=cat)
    r = _bailiff("init", catalog=cat)
    assert r.returncode == 0
    assert "already exists" in r.stdout


# ---------------------------------------------------------------------------
# add / remove
# ---------------------------------------------------------------------------


def test_catalog_add_creates_file_on_no_file_machine(tmp_path: Path) -> None:
    cat = tmp_path / "catalog.toml"
    assert not cat.exists()
    r = _bailiff("add", "user/my-template", catalog=cat)
    assert r.returncode == 0
    assert cat.is_file()


def test_catalog_add_idempotent(tmp_path: Path) -> None:
    cat = tmp_path / "catalog.toml"
    _bailiff("add", "user/my-template", catalog=cat)
    r = _bailiff("add", "user/my-template", catalog=cat)
    assert r.returncode == 0
    assert "already present" in r.stdout


def test_catalog_remove_idempotent(tmp_path: Path) -> None:
    cat = tmp_path / "catalog.toml"
    _bailiff("add", "user/my-template", catalog=cat)
    _bailiff("remove", "user/my-template", catalog=cat)
    # Second remove is a no-op, still exit 0.
    r = _bailiff("remove", "user/my-template", catalog=cat)
    assert r.returncode == 0
    assert "not found" in r.stdout


def test_catalog_add_remove_preserve_other_sources(tmp_path: Path) -> None:
    cat = tmp_path / "catalog.toml"
    _bailiff("add", "user/alpha", "--name", "ptr", catalog=cat)
    _bailiff("add", "user/beta", "--name", "ptr", catalog=cat)
    _bailiff("remove", "user/alpha", "--name", "ptr", catalog=cat)
    data = tomllib.loads(cat.read_text())
    sources = data["catalog"][0]["sources"]
    assert "user/alpha" not in sources
    assert "user/beta" in sources


# ---------------------------------------------------------------------------
# list / list --json
# ---------------------------------------------------------------------------


def test_catalog_list_requires_existing_file(tmp_path: Path) -> None:
    cat = tmp_path / "nonexistent.toml"
    r = _bailiff("list", catalog=cat)
    assert r.returncode == 1
    assert "error" in r.stderr.lower()


def test_catalog_list_json_shape(multi_source_catalog: MultiSourceCatalog) -> None:
    r = _bailiff("list", "--json", catalog=multi_source_catalog.catalog_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    payload = json.loads(r.stdout)
    assert "catalogs" in payload
    cat = payload["catalogs"][0]
    assert "name" in cat
    assert "templates" in cat
    assert "unusable" in cat


def test_catalog_list_json_has_usable_templates(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    r = _bailiff("list", "--json", catalog=multi_source_catalog.catalog_path)
    payload = json.loads(r.stdout)
    full_ids = {t["full_id"] for t in payload["catalogs"][0]["templates"]}
    assert "mycat/tpl-alpha" in full_ids
    assert "mycat/tpl-beta" in full_ids


def test_catalog_list_json_deterministic(multi_source_catalog: MultiSourceCatalog) -> None:
    """Running list --json twice produces byte-identical output (SC-002)."""
    r1 = _bailiff("list", "--json", catalog=multi_source_catalog.catalog_path)
    r2 = _bailiff("list", "--json", catalog=multi_source_catalog.catalog_path)
    assert r1.returncode == 0
    assert r2.returncode == 0
    assert r1.stdout == r2.stdout


def test_catalog_list_human_includes_catalog_name(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    r = _bailiff("list", catalog=multi_source_catalog.catalog_path)
    assert r.returncode == 0
    assert "mycat" in r.stdout


# ---------------------------------------------------------------------------
# per-source failure isolation (FR-005)
# ---------------------------------------------------------------------------


def test_catalog_list_per_source_failure_isolation(tmp_path: Path) -> None:
    """One bad source must not abort the listing; the good source still appears."""
    good = build_template_repo(
        tmp_path / "good-tpl",
        files={"copier.yml": _SIMPLE_COPIER_YML, "template/out.txt.jinja": "x\n"},
        tag="v1.0.0",
    )
    cat_path = tmp_path / "catalog.toml"
    data = {
        "catalog": [
            {
                "name": "testcat",
                "sources": [good.url, "/nonexistent/path/that/does/not/exist"],
            }
        ]
    }
    cat_path.write_bytes(tomli_w.dumps(data).encode())

    r = _bailiff("list", "--json", catalog=cat_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    payload = json.loads(r.stdout)
    cl = payload["catalogs"][0]
    assert any(t["full_id"] == "testcat/good-tpl" for t in cl["templates"])
    assert len(cl["unusable"]) >= 1


# ---------------------------------------------------------------------------
# validate exit codes
# ---------------------------------------------------------------------------


def test_catalog_validate_exit_0_for_valid_id(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    r = _bailiff("validate", "mycat/tpl-alpha", catalog=multi_source_catalog.catalog_path)
    assert r.returncode == 0


def test_catalog_validate_exit_1_for_unknown_id(
    multi_source_catalog: MultiSourceCatalog,
) -> None:
    r = _bailiff("validate", "mycat/ghost", catalog=multi_source_catalog.catalog_path)
    assert r.returncode == 1
    assert "error" in r.stderr.lower()


def test_catalog_validate_exit_1_for_ambiguous_bare_name(tmp_path: Path) -> None:
    # Same basename under different parents → same short name, two pointers → ambiguous.
    repo_a = build_template_repo(
        tmp_path / "group-a" / "tpl-shared",
        files={"copier.yml": _SIMPLE_COPIER_YML, "template/out.txt.jinja": "x\n"},
        tag="v1.0.0",
    )
    repo_b = build_template_repo(
        tmp_path / "group-b" / "tpl-shared",
        files={"copier.yml": _SIMPLE_COPIER_YML, "template/out.txt.jinja": "x\n"},
        tag="v1.0.0",
    )
    data = {
        "catalog": [
            {"name": "c1", "sources": [repo_a.url]},
            {"name": "c2", "sources": [repo_b.url]},
        ]
    }
    cat_path = tmp_path / "catalog.toml"
    cat_path.write_bytes(tomli_w.dumps(data).encode())

    r = _bailiff("validate", "tpl-shared", catalog=cat_path)
    assert r.returncode == 1
    assert "ambiguous" in r.stderr.lower()


# ---------------------------------------------------------------------------
# SC-005: no bailiff artifact written outside --catalog path
# ---------------------------------------------------------------------------


def test_no_bailiff_file_written_outside_catalog_path(tmp_path: Path) -> None:
    """Catalog ops must not write any file outside the --catalog path."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    cat = tmp_path / "catalog.toml"

    _bailiff("init", catalog=cat)

    written = [str(p) for p in tmp_path.rglob("*") if p.is_file() and p != cat]
    assert written == [], f"unexpected files written: {written}"
