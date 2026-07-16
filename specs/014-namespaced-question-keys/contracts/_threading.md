# Contract — private-by-default answer threading (spec 014)

Replaces the run-time cross-layer answer bleed. This is the core engine contract (013 governed C-11
exception). 014's engine footprint is broader than threading alone — it also adds `_external_data`
validation + the stratified-DAG ordering rewrite + the `_bailiff_schema` migration gate (see
[`_facts.md`](./_facts.md) and the Dependency model section below).

## The rule (FR-001, FR-002)

A question key is **PRIVATE** to the module that declares it. `init_many` MUST NOT thread a
layer's private answers into any subsequent layer's `data=`.

Grounded in `src/bailiff/runner.py`:
- line 457: `data = {**accumulated, **layer_answers}` renders each layer.
- line 484: `_merge_layer_answers(accumulated, dest, af_name)` grows `accumulated` with every
  non-`_` key of the just-rendered layer (definition at line 532).
- Result today: every later layer sees every earlier layer's private answers → poisoning.

**Change:** `accumulated` MUST NOT accrete per-layer private answers. `accumulated` is seeded ONLY
with `today` (runner.py:430) and grows solely via `_merge_layer_answers`; there is NO run-level
`--data` channel in the input model (the multi-run-spec exposes only per-layer `answers`, cli.py:286
— VERIFIED). So the change is simply: `accumulated` stays `{today}` and never accretes. Each layer N
renders with:
1. its own per-layer answers (`layer_answers` for that `full_id`);
2. copier/bailiff builtins + run-ordering keys + `today`;
3. any facts it reads via `_external_data` (copier resolves these from the producer's answers file).

`_merge_layer_answers` is neutered (no-op) or removed at its call site (line 484). `today` is the one
legitimately-threaded value and stays in the seed; a sibling layer's answered question never leaks.

## Reproduce parity (FR-003)

`reproduce_many` (runner.py:554) and its accumulator MUST apply the SAME isolation. Reproduce
reconstructs per-layer isolation — each layer replays its OWN `.copier-answers.<basename>.yml` —
NOT a flattened namespace. A committed tree reproduces per-layer.

## Cross-module values move via `_external_data`, not `accumulated`

After this change, cross-module VALUES do not travel through `accumulated` at all. A consumer that
needs a producer's value declares a copier `_external_data` alias (see [`_facts.md`](./_facts.md));
copier reads the producer's answers file directly at render time. This is copier-native, needs no
threading, and is isolated under the alias namespace.

## Invariant (SC-001, SC-002, SC-007)

For any two layers A and B that declare the same bare key `q` with disjoint domains, A's answer for
`q` MUST NOT enter B's render context. Proven by a negative isolation loop test: a two-layer
selection where A defines `q ∈ {x,y}` and B defines `q ∈ {m,n}` inits with no `InvalidRunSpecError`,
and each layer's answers file records only its own `q`. The shipped Python+TS `framework` regression
MUST pass on isolation ALONE (without the merged point-fix rename).

## Dependency model — single edge + stratified DAG (FR-019, FR-020; decisions-ledger R6–R10)

Two DISTINCT dependency kinds, both hard-enforced:
- **Data dependency** — a `_external_data` read (see `_facts.md`): producer required present + ordered
  before consumer; absent → loud error. bailiff statically parses `_external_data` (FR-006a: literal
  `.copier-answers.<basename>.yml` only) to derive the producer.
- **Side-effect dependency** — `depends_on`: X needs Y's side effect (a tool Y installed, a file Y
  wrote that X modifies) WITHOUT reading Y's answers. `depends_on` = target present + ordered-before;
  absent → loud `OrderingError` (existing dangling-edge behavior, made explicit).

**Single edge (FR-019):** `ordering.py` collapses to ONE edge, `depends_on`. `run_after` and
`run_before` are DROPPED (today `depends_on`/`run_after` are byte-identical in code and only
`run_after: base` is used; `run_before` has zero uses and doubles cycle surface). The ~23
`run_after: bailiff-mod-base` migrate to `depends_on: bailiff-mod-base`.

**Stratified DAG (FR-020):** modules carry a phase `pre | normal(default) | post`. Sort = (phase) →
(`depends_on` DAG) → (basename). Edge legality VALIDATED at discovery: pre→pre only; normal→pre+normal;
post→anything; a forward cross-phase edge is rejected (cycles cannot cross phases). `base = pre`;
family = `normal`; `post` reserved for a future finalizer. Solves "run first" structurally.

**Post-tasks (FR-021; R11):** a module MAY declare `_post_tasks` (a `when:false` hidden list, statically
read like edges). bailiff COLLECTS `_post_tasks` across all modules and runs them AFTER the whole render
loop, in `depends_on` order, on BOTH init AND reproduce. This is DISTINCT from the module `phase`: phase
orders whole-module RENDERS; `_post_tasks` defers WORK. It exists because copier runs inline `_tasks` at
each layer's own render (`runner.py:461`) — so a module ordered FIRST (e.g. precommit, a `hook_manager`
producer) cannot run a merge that needs LATER layers' output via an inline task. As a post-task the merge
runs after every fragment exists. The pre-commit bundler + gitignore concat use this. NO `_pre_tasks`
("run first" = be the first module + a normal `_task`, as base's preflight already does). Enabled by
bailiff driving copier as a LIBRARY (`runner.py:33`) — it owns the loop.

## Migration gate (FR-014; R10)

copier silently ignores unknown recorded answer keys (`load_answersfile_data` returns `{}`), so a
pre-014 tree with `mise_tools:` recorded would reproduce WITHOUT tools and WITHOUT error. Post-014
answers files carry `_bailiff_schema: 014`; `reproduce_many` REFUSES (loud error + re-init guidance) on a
missing/older marker. **bailiff writes the marker itself post-render** — it CANNOT be a copier answer (a
`when:false` question is omitted from the file `_main.py:616`; an askable one drops the `_` + pollutes the
namespace + is user-overridable; `--data _key` is stripped by the `startswith("_")` filter). Mirrors how
copier writes `_commit`/`_src_path`. POSITIVE allowlist (pre-014 can't have it; generalizes to 015+).

## What this replaces in the 011 cross-cutting contract

011 §6 states "everything a module CAN get from an upstream layer uses `default: "{{ upstream_answer }}"`
threading via the `init_many` accumulator." Under 014 that threading is REMOVED; upstream values are
read via `_external_data` aliases instead (FR-018 rewrite of §6). 011's edge vocabulary
(`run_after`/`run_before`) is also superseded by the single `depends_on` edge + phases.
