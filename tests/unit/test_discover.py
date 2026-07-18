"""Unit tests for static discovery (US3: FR-001..004a, FR-016a)."""

from __future__ import annotations

import pytest

from bailiff.discovery import discover, list_versions, resolve_locator
from bailiff.errors import DiscoveryError
from tests.conftest import TemplateRepo, build_template_repo


class TestResolveLocator:
    """A bare ``owner/repo`` GitHub shorthand must expand to a clonable HTTPS URL;
    every other locator form passes through untouched (the documented SKILL
    shorthand ``gituser/gitrepo`` otherwise fails: plain git treats it as a local
    path)."""

    def test_bare_owner_repo_expands_to_github_https(self) -> None:
        assert (
            resolve_locator("bailiff-io/bailiff-mod-base")
            == "https://github.com/bailiff-io/bailiff-mod-base.git"
        )

    def test_owner_repo_with_dots_and_dashes(self) -> None:
        assert resolve_locator("acme/x-y_z.t") == "https://github.com/acme/x-y_z.t.git"

    @pytest.mark.parametrize(
        "locator",
        [
            "https://github.com/bailiff-io/bailiff-mod-base.git",
            "git@github.com:bailiff-io/bailiff-mod-base.git",
            "ssh://git@example.com/x/y.git",
            "file:///srv/templates/x",
            "gh:bailiff-io/bailiff-mod-base",
            "gl:group/project",
        ],
    )
    def test_urls_and_host_shorthands_pass_through(self, locator: str) -> None:
        assert resolve_locator(locator) == locator

    @pytest.mark.parametrize(
        "locator",
        ["/abs/path/mod", "./rel/mod", "../up/mod", "~/mod", "C:/win/mod"],
    )
    def test_path_forms_pass_through(self, locator: str) -> None:
        assert resolve_locator(locator) == locator

    def test_existing_local_path_passes_through(self, tmp_path) -> None:
        # A single-slash string that is actually an existing path is NOT a shorthand.
        import os

        (tmp_path / "owner" / "repo").mkdir(parents=True)
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            assert resolve_locator("owner/repo") == "owner/repo"
        finally:
            os.chdir(cwd)

    def test_deep_path_is_not_shorthand(self) -> None:
        # More than one slash → never a GitHub owner/repo shorthand.
        assert resolve_locator("a/b/c") == "a/b/c"


def test_discovery_reports_questions_with_all_fields(base_template: TemplateRepo) -> None:
    d = discover(base_template.url)
    by_key = {q.key: q for q in d.questions}
    # every documented question field is present
    assert set(by_key) == {"project_name", "org", "license", "description", "today"}
    lic = by_key["license"]
    assert lic.type == "str"
    assert lic.choices == ["MIT", "Apache-2.0"]
    assert lic.default_raw == "Apache-2.0"
    assert lic.secret is False


def test_defaults_reported_raw_unrendered(tmp_path) -> None:
    # A default that is a Jinja expression MUST be reported verbatim, never evaluated
    # (FR-004a) — evaluating it would require building the engine env.
    repo = build_template_repo(
        tmp_path / "tpl",
        files={
            "copier.yml": (
                "project_name:\n  type: str\n"
                'slug:\n  type: str\n  default: "{{ project_name | lower }}"\n'
                "_subdirectory: template\n"
            ),
            "template/out.txt.jinja": "{{ slug }}\n",
        },
    )
    d = discover(repo.url)
    slug = next(q for q in d.questions if q.key == "slug")
    assert slug.default_raw == "{{ project_name | lower }}"


def test_secret_flag_and_hidden_edges(secret_edge_template: TemplateRepo) -> None:
    d = discover(secret_edge_template.url)
    keys = {q.key for q in d.questions}
    # the secret question is a visible question and flagged; the when:false edge is NOT
    assert "api_token" in keys
    assert d.secret_questions == ["api_token"]
    assert "depends_on" not in keys
    assert d.dependency_edges.get("depends_on") == ["bailiff-mod-base"]


def test_reproducible_flag_true_when_answers_file_present(base_template: TemplateRepo) -> None:
    assert discover(base_template.url).reproducible is True


def test_reproducible_flag_false_when_answers_file_absent(
    no_answers_file_template: TemplateRepo,
) -> None:
    assert discover(no_answers_file_template.url).reproducible is False


def test_has_tasks_flag(base_template: TemplateRepo) -> None:
    assert discover(base_template.url).has_tasks is True


def test_versions_filtered_to_pep440(tmp_path) -> None:
    repo = build_template_repo(
        tmp_path / "tpl",
        files={
            "copier.yml": "x:\n  type: str\n_subdirectory: template\n",
            "template/x.txt.jinja": "x\n",
        },
        tag="v1.0.0",
    )
    # add a second valid tag and a junk tag copier would ignore
    from tests.conftest import _git

    _git(repo.path, "tag", "v1.2.0")
    _git(repo.path, "tag", "nightly")  # non-PEP440 → must be filtered out
    versions = list_versions(repo.url)
    assert versions == ["v1.0.0", "v1.2.0"]
    assert "nightly" not in versions


def test_refuses_source_with_no_usable_version(tmp_path) -> None:
    # A repo whose only tag is non-PEP440 → discovery refuses (FR-016a).
    from tests.conftest import _git

    repo_root = tmp_path / "tpl"
    repo = build_template_repo(
        repo_root,
        files={
            "copier.yml": "x:\n  type: str\n_subdirectory: template\n",
            "template/x.txt.jinja": "x\n",
        },
        tag="v1.0.0",
    )
    # delete the only PEP440 tag, leave a junk one
    _git(repo.path, "tag", "-d", "v1.0.0")
    _git(repo.path, "tag", "nightly")
    with pytest.raises(DiscoveryError, match="no usable version"):
        discover(repo.url)


def test_to_dict_is_json_serializable(base_template: TemplateRepo) -> None:
    import json

    d = discover(base_template.url)
    # round-trips through JSON — this is the documented agent-facing shape (FR-004)
    payload = json.dumps(d.to_dict())
    assert json.loads(payload)["reproducible"] is True
