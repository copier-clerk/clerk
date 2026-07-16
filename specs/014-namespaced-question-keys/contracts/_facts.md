# Contract — cross-module facts via `_external_data` aliases (spec 014)

Replaces 011 cross-cutting §6's `default: "{{ upstream_answer }}"` threading and the frozen-union
model. A cross-module VALUE (fact) is read through copier `_external_data`, never threaded.

## Authoring pattern (FR-004)

A consumer that needs a value another module produced declares a local alias pointing at the
producer's deterministic answers file, and reads it through the alias namespace:

```yaml
# consumer module copier.yml
_external_data:
  base: .copier-answers.bailiff-mod-base.yml     # producer's answers file (deterministic name)

project_name:
  type: str
  default: "{{ _external_data.base.project_name }}"   # base is a HARD dependency (see FR-006)
```

- The producer writes the key to its OWN answers file as a NORMAL bare question — no prefix, no
  special declaration.
- The borrowed value lives under the alias namespace (`_external_data.base.project_name`); copier
  isolates it structurally — it never enters the consumer's question namespace or answers file.
- **No vendor prefix** (FR-007): the `<vendor>__<name>` scheme is rejected. **No shared-key lint**:
  `check_modules.py` gains none.
- **The `_external_data` path MUST be a literal `.copier-answers.<basename>.yml`** (FR-006a) so bailiff
  can statically map the alias to a producer basename and enforce the dependency (below).

## Producer path is a stable contract (FR-005)

The per-layer answers file is `.copier-answers.<module-basename>.yml`
(`ordering.py:answers_file_name`). A consumer hard-codes the producer basename in its alias. This
name is a stable contract; changing the scheme is a separately-gated breaking change.

## A fact read is a HARD data-dependency (FR-006, INVERTED)

Reading `_external_data.<alias>.<key>` makes the aliased producer a HARD dependency. bailiff
statically parses the consumer's `_external_data` block, maps each alias → producer basename, and at
preflight:
- producer ABSENT from the selection → LOUD error (reuse `OrderingError`, naming the alias);
- producer PRESENT → ordered before the consumer (the data-dependency IS an ordering constraint).

**No graceful fallback.** The prior "fall back to own default" rule is REPLACED: copier's behavior on
a missing external-data file is `warn + return {}` (`_user_data.py:597-603`), so unguarded
`{{ _external_data.base.project_name }}` renders EMPTY STRING — the silent mis-render SC-006 forbids.
bailiff produces the error copier will not. A module that renders `project_name` genuinely NEEDS a
producer; requiring it is honest. (decisions-ledger R6 + "FR-006 INVERTED".)

## The ratified first-party fact set (FR-007 / R4 — EXPANDED after exhaustive audit)

Producers = **base + precommit + ts + moon**. Exhaustive audit confirmed NO facts beyond this set.

### base-produced (alias `base` → `.copier-answers.bailiff-mod-base.yml`)

| fact | consumers wiring an alias |
|---|---|
| `project_name` | agentic, api, apm, cdk, ci-gitlab, cocogitto, devcontainer, github-repo, gitlab-repo, go, mkdocs, moon, python, readme, rust, stack-adr, ts, terraform |
| `layout` | moon, cocogitto, package-add |
| `description` | apm, api, mkdocs, python, readme |
| `default_branch` **(NEW to base)** | ci-github, ci-gitlab |

- `default_branch` MUST be added to `bailiff-mod-base/copier.yml` (fixes a latent bug: ci-github
  `copier.yml:80-82` / ci-gitlab `:91-93` thread it from a non-existent producer today).
- `description` KEPT + made a base fact; the 5 consumers read `_external_data.base.description`.
- **`github_host` is NOT a base fact (R12/FR-022).** It was previously listed here (consumer:
  dep-updates), but R12 DELETES `github_host` from base — forge metadata (`.github/`) moves to the forge
  modules, base emits no forge files, and dep-updates self-defaults `dep_update_tool` rather than reading
  a base fact. No `_external_data.base.github_host` alias exists. Base fact count is 4.

### precommit-produced (alias `precommit` → `.copier-answers.bailiff-mod-precommit.yml`)

| fact | consumers |
|---|---|
| `hook_manager` | python, ts, api, go, rust, terraform, justfile |

Precommit co-occurs with language overlays in the same stack — a genuine non-exclusive cross-layer
read (found by the critique; missed by the first audit). Reading it auto-requires precommit present.

### ts-produced (alias `ts` → `.copier-answers.bailiff-mod-ts.yml`)

| fact | consumers |
|---|---|
| `js_pkg_manager` | justfile, package-add |
| `ts_linter` | editorconfig |

### moon-produced (alias `moon` → `.copier-answers.bailiff-mod-moon.yml`)

| fact | consumers |
|---|---|
| `monorepo_tool` | ci-github, ci-gitlab |
| `monorepo_packages` | ci-gitlab, cocogitto |

Proves the mechanism is not base-specific.

### Bare-private — NOT facts, no alias

- `org`, `copyright_name`, `branch_strategy` — base-only, no cross-layer reader.
- Exclusive-sibling keys — `visibility`/`remote_protocol`/`push_after_create`/`team` (github-repo vs
  gitlab-repo); `ci_*` (ci-github vs ci-gitlab); `placement_dir` (terraform/cdk/cloudformation). One
  of each mutually-exclusive sibling per stack; never co-occur.

### Collision-class — stay PRIVATE (reading them cross-layer IS the bug)

- `test_runner` — go `{go-test,gotestsum}` vs rust `{cargo-test,nextest}` vs ts
  `{none,vitest-*,bun-test,playwright-only}`: DISJOINT domains. Private-by-default fixes it wholesale.

## Edge cases

- **Promoting a private key to a fact later**: no rename — the producer already writes it; a consumer
  opts in by adding an alias + read (which then REQUIRES the producer present).
- **A fact whose producer is absent**: LOUD preflight error (FR-006), never a silent empty render.
