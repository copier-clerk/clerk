# Contract — clerk multi-template ordering + recomputed reproduce (spec 003)

clerk applies several templates to one project in dependency order and recomputes
that order at reproduce from committed state. copier does zero cross-template
coordination; clerk is the ordering brain (ADR-0003). Nothing clerk-authored is
committed to encode the order (spec 010 / Constitution III).

## The multi-template run-spec

An extension of the 001 single-template run-spec: a **selection** (≥1 template) plus
per-layer answers. `today` is injected by clerk (unchanged). Single-template is the
N=1 case of this shape.

```yaml
dest: "./my-project"
selection:
  - full_id: "demo/clerk-mod-base"      # from spec 002 catalog validate
    source: "https://github.com/…/clerk-mod-base.git"   # resolved locator
    ref: "v1.2.0"                        # optional pin (else latest)
    answers: { project_name: acme, license: MIT }
  - full_id: "demo/clerk-mod-python"
    source: "https://github.com/…/clerk-mod-python.git"
    ref: null
    answers: { python_version: "3.12" }  # may reference an earlier layer's answer via copier default
```

- The agent authors this from the validated selection (spec 002) + collected answers.
- Per-layer `answers` thread forward: clerk accumulates them and passes the running
  dict as `data=` into each subsequent `copier copy` (NOT `_external_data` — ADR-0003).

## Dependency edges (inputs to the DAG)

Read statically from each template's `copier.yml` as hidden `when:false` answers
(already parsed into `discovery.Discovery.dependency_edges`):

- `depends_on: [X, …]` — this template must apply AFTER X. Edge: X → self.
- `run_after: [X, …]` — same direction as `depends_on`. Edge: X → self.
- `run_before: [Y, …]` — this template must apply BEFORE Y. Normalized to: self → Y.

Edges reference templates by a name matching the selection's identity (full-id or
its basename — the resolver documents which; see "Identity matching"). An edge to a
template **not in the selection** is a *dangling edge* → refused (Q-003b: refuse,
name it).

## Order algorithm

1. Build a directed graph: nodes = selected layers; edges from the normalized
   declarations above.
2. **Refuse before any write** (raise `OrderingError`): a cycle (name the cycle), a
   dangling edge (name the missing dependency), or a basename collision among
   selected templates (two layers wanting the same `.copier-answers.<basename>.yml`).
3. **Topologically sort** with a **stable tie-break**: among nodes with no ordering
   constraint between them, order **lexicographically by full-id** (globally unique
   per spec 002 ⇒ a total, deterministic order). Use `graphlib.TopologicalSorter`
   (feeding ready-sets in tie-break order) or an equivalent Kahn's algorithm.
4. The result is the layer application order — computed identically at init and at
   reproduce.

**Determinism**: pinned commits → identical edges → identical graph → identical
sort (same tie-break). Edge-independent layers writing disjoint paths therefore
produce byte-identical output regardless of the selection's input order.

## Init (apply the layers)

`runner.init_many(selection, dest, *, today, check)`:

1. Compute order (above).
2. For each layer in order, `run_copy(source, dest, data=<accumulated answers +
   today>, vcs_ref=ref, answers_file=".copier-answers.<basename>.yml", defaults=True,
   overwrite=True, quiet=True, pretend=check)`.
3. Merge that layer's answers into the accumulating `data=` dict for later layers.
4. Each layer commits its own `.copier-answers.<basename>.yml` recording its
   `_src_path` + `_commit`. **No clerk-authored order file is written.**

`--check` runs step 2 with `pretend=True` for every layer (the all-gaps preflight)
and writes nothing.

## Reproduce (recompute the order)

`runner.reproduce_many(dest)`:

1. `enumerate_answers_files(dest)` → the committed `.copier-answers*.yml` layers
   (spec 010, already implemented).
2. For each, read its recorded `_src_path` + `_commit`; **re-discover** the template
   at that pinned commit (static parse) to re-read its edges.
3. Rebuild the DAG + topo-sort with the **same stable tie-break** → the recomputed
   order.
4. For each layer in that order, `runner.reproduce(dest, answers_file=<that file>)`
   (spec 010's existing per-layer recopy at `VcsRef.CURRENT`).

- Uses ONLY the committed answers files + pinned re-fetches. No recipe/DAG file is
  read or required (FR-005).
- **copier-only-by-hand fallback**: a human without clerk runs `copier recopy
  --vcs-ref=:current: --defaults --overwrite -a <each .copier-answers*.yml>` in the
  recomputed order; the order is derivable by hand from the same committed edges.
  (clerk automates it; nothing about the project *requires* clerk — spec 010.)
- Reproduce resolves only from recorded pins; a dependency added in a newer template
  version is NOT picked up (that is `update`, spec 006 — FR-009).

## Identity matching (edges ↔ selection)

Edge targets are matched to selected layers by **template basename** (the repo
name), which is also the answers-file key. Because a basename collision among
selected templates is refused (above), basename is an unambiguous key *within a
valid selection*. (Full-id is the catalog identity; the edge, authored inside a
template's `copier.yml`, names sibling templates by basename — the portable name a
template author knows without knowing the consumer's catalog.)

## Exit codes (multi-template surface)

| Code | Meaning |
|---|---|
| 0 | success (or `--check` clean) |
| 1 | `OrderingError` (cycle / dangling edge / basename collision) or other `ClerkError` (bad run-spec, copier failure) |
| 2 | argparse usage error |
| 3 | `UntrustedSourceError` — a layer takes actions from an untrusted source |

`OrderingError` messages MUST name the offending relation (the cycle members, the
missing dependency, or the colliding basename) so the user can fix the selection.
