---
description: "Task list — spec 016: whole-plan tool-preflight gate (_bailiff_requires + engine which() check)"
---

# Tasks: Whole-plan tool-preflight gate (spec 016)

**Input**: `specs/016-tool-preflight-gate/` — spec.md (FR-001..008, SC-001..006), plan.md.

**Prerequisites**: branch off `origin/main` (carries the 014/015 engine + 0.4.2 fixes).
spec + plan RATIFIED.

**Tests**: SC-001..006 name behaviors; test tasks INCLUDED, fail-first before the gate lands.

## Format: `[ID] [P?] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- Engine: `src/bailiff/{discovery,runner}.py`; tests `tests/unit/`, `tests/loop/`.

---

## Phase 1: Setup

- [ ] T001 Confirm branch on origin/main; run non-network baseline DETACHED; record pass count.
- [ ] T002 `uv run python scripts/check_modules.py` → record module-count baseline.

## Phase 2: Discovery (FR-001/002/003)

- [ ] T003 discovery: parse `_bailiff_requires` → `Discovery.requires: list[dict[str,str]]`,
  normalizing a bare string to `{tool, when: ""}` and a `{tool, when?}` map likewise;
  validate each entry (str | mapping with str `tool`, optional str `when`; unknown key →
  DiscoveryError naming module+entry). Add to `to_dict()`. `src/bailiff/discovery.py`.
- [ ] T004 [P] Tests (fail-first) `tests/unit/test_discover.py`: bare + mapping forms parse;
  unconditional vs `when`; malformed (non-str tool / unknown key / non-list) fail loud;
  absent field → `[]`; surfaces in `to_dict()`.

## Phase 3: Engine gate (FR-004/005/006)

- [ ] T005 runner: `_check_required_tools(plan, answers_by_layer)` — for each layer, for each
  `requires` entry whose `when` (if set) is truthy in that layer's answers, `shutil.which(tool)`;
  collect all misses; raise one BailiffError listing `tool — needed by <module>` per line.
  `src/bailiff/runner.py`.
- [ ] T006 runner: call the gate in `init_many` AFTER `_check_external_data_deps` /
  `_scan_init_collisions` and BEFORE the render loop; also in single `init` before `run_copy`;
  runs for `check=True` too (FR-006). Pass each layer's `{**today, **answers}`.
- [ ] T007 [P] Tests (fail-first) `tests/loop/test_tool_preflight.py`: (a) a module requiring an
  absent tool → init fails BEFORE any write (dest empty/absent), error names tool+module
  (SC-001); (b) two missing tools → one error names both (SC-002); (c) `when`-gated tool absent
  with opt-out answer → succeeds, with opt-in → fails (SC-003); (d) `--check` surfaces the miss
  without writing (SC-005); (e) reproduce of a present-tools project unaffected (SC-006).

## Phase 4: Module declarations (FR-001, SC-004)

- [ ] T008 Add `_bailiff_requires` to every task-bearing first-party module, matching the
  binary each declares directly OR the `mise` gate for the mise-install chain:
  - direct: lefthook→`{lefthook, when: install_hooks}`, precommit→`{pre-commit, when:
    install_hooks}`, cloudformation→`{aws, when: aws_validate}`, base→`git`/`gh`/`gitnr`,
    github-repo→`gh`, gitlab-repo→`glab`, apm→`uvx`.
  - mise-gated: python/ts/moon/cocogitto/go/rust/cdk/agentic/package-add/terraform → `mise`
    (the provisioned tools are mise's job, D2). Add the value-conditional extras (uv/pdm,
    cargo, go) only as the mise gate unless a bare `when` key fits.
- [ ] T009 Rebuild affected module loop fixtures if any assert `_tasks` shape (unlikely — the
  field is additive metadata). Confirm existing loop/stack tests still pass.

## Phase 5: Validation + docs (FR-008)

- [ ] T010 `scripts/check_modules.py`: validate `_bailiff_requires` shape across all modules
  (list of str | {tool, when?} with str values); absent is allowed. Record 28-module pass.
- [ ] T011 [P] `_cross-cutting.md` + SKILL.md: document `_bailiff_requires` as the canonical
  required-tools declaration, paired with the `command -v` `_task` backstop; re-vendor SKILL.md.

## Phase 6: Ship

- [ ] T012 Full non-network suite DETACHED → 0 failures + new SC tests. Fast gates:
  ruff/format/mypy, check_modules ok, doctor Ready.
- [ ] T013 PR → main; on green CI merge (fires fan-out for the touched modules + release-please
  engine bump). Verify mirrors + PyPI.

## Dependencies

- T003 before T005 (gate reads `Discovery.requires`).
- T005 before T006; T006 before T007.
- T008 after T006 (declarations are exercised by the gate).
- T010/T011 after T008; T012 after all.
