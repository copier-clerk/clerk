# Contract — `_agent_tasks` / `_post_agent_tasks` (spec 015)

The manifest fields, init/reproduce timeline, engine freeze, and reproduce-safety lint
for agent-projected capability work. Governs FR-001..012. Builds on the spec-014 engine
(`_post_tasks`, phase/`depends_on` ordering, `_bailiff_schema`).

## 1. Manifest schema

A module MAY declare either or both fields at the top level of `copier.yml`, as siblings
to `_tasks`/`_post_tasks`:

```yaml
_agent_tasks:            # paired with the module's inline _tasks (own-module context)
  pre:  "instruction to the agent, run before this module's _tasks"
  post: "instruction, run after this module's _tasks"

_post_agent_tasks:      # paired with the post-loop _post_tasks (full-stack context)
  pre:  "instruction, run before the post-loop mechanical merges"
  post: "instruction, run after the post-loop mechanical merges"
```

Rules:

- Each field is a MAP with optional string values under keys `pre` and `post` only.
- Any other key is a manifest error at discovery (FR-004): fail loud, name the module,
  the field, and the offending key.
- Each value is a freeform natural-language instruction. **bailiff does not parse,
  interpret, or validate it** beyond `isinstance(str)` (FR-003). The map KEYS are the
  schedule — there is no `slot:`/`when:`/`outputs:` sub-structure.
- Absent field, or absent `pre`/`post` key, means that point runs nothing.
- Discovery reports presence in the `Discovery` record (FR-005): `agent_tasks: {pre?,
  post?}` and `post_agent_tasks: {pre?, post?}`, each a dict with the string values that
  were declared (empty dict when the field is absent).

## 2. Init timeline (FR-006 / FR-007)

Ordering is the spec-014 sort: phase (`pre`→`normal`→`post`) → `depends_on` DAG →
basename tie-break. Within the render loop, per module in sort order:

```
render module → _agent_tasks.pre → inline _tasks → _agent_tasks.post
```

After the full render loop, in module sort order across each stage:

```
every _post_agent_tasks.pre → mechanical _post_tasks (per module) → every _post_agent_tasks.post
```

Then the engine writes `_bailiff_schema` markers and (spec 014 fix) runs the
whole-project initial-commit finalizer. Agent `pre`/`post` instructions invoke the
phase-1 AGENT and run at INIT ONLY (FR-008).

## 3. The agent seam (engine stays LLM-free)

The deterministic engine has no LLM. It invokes agent work through an injected callable:

```python
AgentTask = Callable[[str, AgentContext], AgentResult]
# instruction: the verbatim pre/post string from the manifest
# AgentContext: read-only view — dest path, this module's basename, the full
#   selection (module basenames + their answers files), and the current tree.
# AgentResult: a mapping {relative_path: file_content} the agent wrote/wants written.
```

- `runner` accepts the callable as a parameter (default: a binding the CLI/skill
  supplies; tests inject a deterministic stub). This keeps `runner` free of any LLM
  import (Constitution II) while giving init a defined call-out point.
- The agent MUST base its projection on the actual module SELECTION (FR-018) — e.g.
  "project every `.hooks.d/` entry into the selected hook manager's format".
- The engine writes `AgentResult` paths into `dest`, then freezes (below).

## 4. Freeze + replay (FR-009 / FR-010 / FR-011) — a GLOBAL engine rule

Reproduce-safety is the ENGINE's behavior, not an author annotation. There is no
`freeze:`/`outputs:` field on the task.

- **Init:** after an agent task returns, the engine captures its `AgentResult` and writes
  a frozen record to the producing module's answers file, append-only (the same
  mechanism as `_bailiff_schema`):

  ```yaml
  _agent_frozen:
    <slot>:            # one of: agent_tasks.pre, agent_tasks.post,
                       #         post_agent_tasks.pre, post_agent_tasks.post
      <relative_path>: <file_content>
  ```

  The captured shape is OPAQUE to bailiff — it stores and replays it verbatim. The
  record must survive copier's answers-file round-trip (verify like `_bailiff_schema`).

- **Reproduce:** the engine detects `_agent_frozen` and REPLAYS the recorded
  `{path: content}` writes INSTEAD of invoking the agent. All `pre`/`post` agent tasks
  are SKIPPED (FR-010). Mechanical `_tasks`/`_post_tasks` re-run and consume the replayed
  files. No agent, deterministic (Constitution III).

- **Update (re-init):** the agent RE-RUNS against the current selection and RE-FREEZES
  (init-class, not reproduce-class).

## 5. Reproduce-safety lint (FR-012)

An ENGINE check at init, after freezing. For every path an agent task wrote:

- If that path is ALSO produced by a MANAGED render (a template file that re-renders
  byte-identically on reproduce) AND its content was not captured into `_agent_frozen`,
  init FAILS with an error naming the path.

Rationale: on reproduce the managed re-render would overwrite the agent's output, so an
unfrozen agent-owned managed path is a silent-drift bug. The lint is a set check:
`(managed_rendered_paths ∩ agent_written_paths) ⊆ frozen_paths`, else fail loud.

## 6. Determinism / trust (unchanged from 014)

- Same-stage tie-break is module sort order (identical to `_post_tasks`).
- Agent tasks run under the same per-module trust gate as `_tasks`/`_post_tasks`
  (`has_tasks` is true when any agent-task field is present).
- Agent instructions carry NL only, never secrets (Constitution V); `AgentContext`
  exposes answers files but the agent MUST NOT emit secret values into frozen records.

## 7. Test shape

- Discovery: valid `pre`/`post` parse; a non-`pre`/`post` key fails loud (FR-004).
- Timeline: a stub agent that appends a marker per slot proves ordering
  (render→pre→_tasks→post; post-loop pre→_post_tasks→post) in module sort order.
- Freeze/replay: init with the stub captures `_agent_frozen`; reproduce with a
  RAISING stub (asserts the agent is never called) reproduces byte-consistently.
- Lint: a module whose agent task writes a managed-rendered path without a freeze fails
  init with the path named.
