# Feature Specification: bailiff Single-Module Vertical Slice

**Feature Branch**: `001-bailiff-vertical-slice`

**Created**: 2026-07-09

**Status**: Draft

**Input**: Roadmap spec 001 (`.specify/memory/roadmap.md`). Governed by the
constitution (`.specify/memory/constitution.md`, Principles I–VIII) and ADRs
0001/0002/0004 in `docs/decisions/`.

## Overview

bailiff is an agentic conductor for the copier scaffolding engine. This first slice
proves the entire bailiff value loop end-to-end at the smallest honest scale: one
source repository holding one template, discovered, filled in by an assisting
agent, rendered once, and later regenerated faithfully with no agent involved.

The work is split at a fixed boundary. An **assistant (phase 1)** does only the
judgment work — inspecting the template, presenting its questions to a person,
collecting answer values, and obtaining consent to trust a source. A
**deterministic phase 2** — copier's own command-line interface, plus a little glue
for what it and the assistant cannot do directly — does everything mechanical:
validating the collected inputs (via copier's dry run), driving copier to render,
and reproducing the result. The assistant is never involved when a project is
reproduced.

bailiff here is **an assistant skill + one example copier template + minimal
deterministic glue** — not a standalone application. copier already performs init,
reproduce, and trust refusal each as a single command; bailiff adds the conducting
procedure, the template, and only the small pieces copier does not expose directly
(static template inspection, a dry-run check, and a version-pinned reproduce
recipe).

Success for this slice is a single, demonstrable journey: a person points the
assistant at the example template, answers a handful of project-identity
questions, and receives a rendered, version-controlled, **reproducible** project;
running the reproduce command later regenerates that project faithfully with no
assistant in the loop.

## Clarifications

### Session 2026-07-09

- Q: Faithful reproduce pins to a movable version label (the engine records the tag
  name, not the immutable revision); should this slice record the immutable revision
  too? → A: Document-only. bailiff documents the limitation and the template-author
  contract declares published version labels immutable; no immutable revision is
  recorded and no label-moved check is added in this slice.
- Q: Reproduce runs against an already-generated project; does it overwrite rendered
  files in place, require a clean destination, or warn before clobbering? → A:
  Overwrite-in-place as a fixed invariant. Reproduce always overwrites rendered files
  (local edits to rendered files revert), leaves write-once and unrelated files
  untouched, and never prompts. (Verified: the engine's non-interactive overwrite is
  the only viable mode — without it the engine blocks on an interactive overwrite
  prompt.) Respecting local edits is deferred to the upgrade operation, spec 006.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a reproducible project from one template (Priority: P1)

A developer wants to start a new project from a known template. With the
assistant's help they inspect the template, answer its identity questions
(project name, organization, license, description), and generate the project.
The generated project records exactly which template and version produced it, and
which answers were used, so it can be regenerated later without guesswork.

**Why this priority**: This is the whole reason bailiff exists — turning a template
plus human intent into a concrete, reproducible project. Everything else in the
roadmap builds on this loop. If only this story ships, bailiff already delivers a
usable single-template generator.

**Independent Test**: Point the tool at the example template, supply a complete set
of answers, run generation, and confirm the destination contains the rendered
files, a recorded answers file naming the template and its version, and an
initialized version-control repository.

**Acceptance Scenarios**:

1. **Given** the example template and a complete set of answers, **When** the
   developer generates the project, **Then** the destination contains the rendered
   files (README, license, ignore file, standard directories), a recorded answers
   file capturing the template source, its version, and every supplied answer, and
   an initialized version-control repository.
2. **Given** a completed generation, **When** the developer inspects the recorded
   answers file, **Then** it names the exact template source and the exact version
   used, and it contains the answers the person supplied (but not any answer marked
   secret, and not internal dependency-ordering values).
3. **Given** a set of answers that omits a required question, **When** the developer
   attempts generation, **Then** the tool refuses and reports which required answer
   is missing, in a clear, structured form, without producing a partial project.

---

### User Story 2 - Reproduce an existing project faithfully, without an assistant (Priority: P1)

Later — on another machine, in continuous integration, or for disaster recovery — a
developer or an automated job needs to regenerate the project exactly as it was
first produced, from the recorded answers, with no assistant and no drift to a
newer template version.

**Why this priority**: Faithful, assistant-free reproduction is bailiff's headline
guarantee and the reason the whole two-phase split exists. A generator that cannot
reproduce its output is not bailiff.

**Independent Test**: Take a project produced by Story 1, run the reproduce command
against it, and confirm the regenerated files match the originally rendered files,
that the same template version is used (not a newer one), and that no assistant was
invoked.

**Acceptance Scenarios**:

1. **Given** a project produced by Story 1 and its recorded answers, **When** the
   reproduce command runs, **Then** it regenerates the project from the recorded
   template **version** (the one named in the answers file), not the latest
   available version.
2. **Given** the same project, **When** reproduce runs twice in a row, **Then** the
   rendered file tree is identical between runs (excluding state that a template
   task legitimately obtains from outside the render, which is out of scope for byte
   comparison).
3. **Given** a reproduce run, **When** it executes, **Then** no assistant or
   language-model step participates at any point.
4. **Given** the recorded template version can be resolved, **When** reproduce runs,
   **Then** it never silently advances the project to a newer template version.

---

### User Story 3 - Inspect a template before answering (Priority: P1)

Before answering anything, the assistant needs to know what a template asks for and
whether it is safe and reproducible. It requests a machine-readable description of
the template and uses it to present questions to the person and to author a correct
set of inputs.

**Why this priority**: This is the assistant's only window into the template. Without
a reliable inspection step, the assistant cannot present accurate questions or
produce valid inputs, and the deterministic tool has nothing correct to act on.

**Independent Test**: Run inspection against the example template and confirm the
returned description lists every question (with its type, choices, default, help,
validation, and whether it is secret), the template's declared dependency-ordering
values, whether the template is reproducible (see Story 5), and the template's
available versions — in a documented, machine-readable format.

**Acceptance Scenarios**:

1. **Given** the example template, **When** the assistant requests inspection,
   **Then** it receives a machine-readable description listing each question with its
   type, choices, default, help text, validation, and secret flag; the template's
   declared dependency-ordering values; whether the template ships the mechanism
   required to be reproducible; whether the template runs post-generation actions;
   and the template's available versions.
2. **Given** the inspection description, **When** the assistant reads it, **Then** the
   format conforms to a published, versioned contract so the assistant can rely on
   its shape.

---

### User Story 4 - Consent before a template may take actions (Priority: P1)

The example template runs a post-generation action (it initializes version
control). Templates that take actions can, in general, run arbitrary code, so bailiff
must not run them from a source the person has not explicitly trusted. When
generation is attempted against an untrusted source, the tool stops and explains
exactly what must be trusted; the person decides; only then is trust recorded.

**Why this priority**: Trust governs code execution. Getting consent and its storage
right is a safety-critical part of the loop and is exercised the moment the example
template's action runs.

**Independent Test**: Attempt generation from a source that is not yet trusted and
confirm the tool refuses with a clear, structured message naming the exact source
prefix to trust; then record trust through the tool and confirm generation proceeds.

**Acceptance Scenarios**:

1. **Given** a source that is not trusted and a template that takes actions, **When**
   generation is attempted, **Then** the tool refuses, takes no destructive action,
   and reports the exact source prefix that must be trusted.
2. **Given** the person has consented, **When** trust is recorded through the tool,
   **Then** the recorded trust entry matches the source in the exact form the tool
   uses to fetch it, so that subsequent runs recognize the source as trusted.
3. **Given** an unattended reproduce or continuous-integration run, **When** the
   required trust is absent, **Then** the run fails loudly and never prompts and
   never records trust on its own.
4. **Given** any generation or reproduce run, **When** it needs trust, **Then** the
   deterministic tool never records trust by itself — trust is only ever recorded by
   an explicit, separate consent action.

---

### User Story 5 - Refuse templates that cannot be reproduced (Priority: P2)

A template that does not carry the mechanism needed to record its own answers would
produce a project that can never be faithfully reproduced. Because reproducibility
is bailiff's core promise, the tool detects this during inspection and refuses to
generate from such a template, rather than silently producing an
un-reproducible project.

**Why this priority**: It closes a verified failure mode that would silently break
the headline guarantee. It is P2 only because the example template satisfies the
requirement; the value is in preventing a bad template from slipping through.

**Independent Test**: Attempt to inspect/generate from a template that lacks the
answer-recording mechanism and confirm the tool refuses with a clear, structured
explanation and produces nothing.

**Acceptance Scenarios**:

1. **Given** a template that lacks the mechanism to record its answers, **When**
   inspection runs, **Then** the result reports the template as not reproducible.
2. **Given** such a template, **When** generation is attempted, **Then** the tool
   refuses and reports that the template cannot be reproduced, and no files are
   produced.

---

### User Story 6 - Validate inputs before generating (Priority: P2)

Before committing to a generation, the assistant (or the person) wants to know
whether the collected inputs are complete and valid, without actually producing
anything. A check mode reports problems and changes nothing on disk.

**Why this priority**: It shortens the author-inputs / fix / retry loop and prevents
half-produced projects. It is a distinct, separately testable behavior from
generation.

**Independent Test**: Run the check mode against a complete input set (expect a
clean report and no files produced) and against an input set missing a required
answer (expect a problem report and no files produced).

**Acceptance Scenarios**:

1. **Given** a complete, valid input set, **When** check mode runs, **Then** it
   reports the inputs as valid and produces no files.
2. **Given** an input set missing a required answer, **When** check mode runs,
   **Then** it reports the problem in a structured form and produces no files.
3. **Given** any input problem surfaced by the engine, **When** it reaches the person
   or assistant, **Then** it is presented with a clear, actionable message and a
   non-zero exit — not a bare, context-free stack trace.

---

### Edge Cases

- **Missing required answer**: generation and check both refuse and name the missing
  answer as a structured error; nothing is produced. (In this slice, when several
  required answers are missing, at least the first is reported; reporting *all* gaps
  across multiple templates in one pass is explicitly deferred to a later roadmap
  spec — see Assumptions.)
- **Untrusted source with an action-taking template**: refuse and name the prefix to
  trust; take no destructive action.
- **Trust recorded in a mismatched form**: if the recorded trust entry does not match
  the exact form used to fetch the source, the source is treated as untrusted (the
  tool must record trust in the matching form so this does not happen for its own
  onboarding).
- **Template lacking the answer-recording mechanism**: refuse to generate; report not
  reproducible.
- **Reproduce with the recorded version unresolvable**: fail loudly with a clear
  message; never fall back to a newer version.
- **Post-generation guidance**: if the template provides an after-generation message,
  it is captured and surfaced as a structured field rather than only printed.
- **Destination already contains files**: generation overwrites conflicting rendered
  files (consistent with a non-interactive, answer-driven run); files the template
  marks as write-once are not overwritten. (Reconcile/merge behavior is out of scope
  for this slice.)
- **Reproduce onto an existing tree**: reproduce always runs against an
  already-generated project, overwriting rendered files in place per FR-015a (local
  edits to rendered files revert; write-once and unrelated files untouched), and
  re-runs the post-generation action against existing state; the example action MUST
  be safe to re-run (initializing already-initialized version control is a no-op).
- **Discovery of an untrusted source**: inspection MUST succeed on an untrusted source
  (per FR-004a it executes no template code), so discovery never requires trust; only
  generation/reproduce of an action-taking template does.
- **Engine internals change shape under a compatible upgrade**: the tool's use of
  non-public engine internals is quarantined and guarded so that such a change is
  caught by tests rather than silently misbehaving.

## Requirements *(mandatory)*

### Functional Requirements

**Inspection**

- **FR-001**: The system MUST provide a way to inspect one template at a specified
  source and version and return a machine-readable description of it.
- **FR-002**: The inspection description MUST include, for each question the template
  asks: its identifier, type, allowed choices (if any), default, help text,
  validation, and whether it is a secret.
- **FR-003**: The inspection description MUST include the template's declared
  dependency-ordering values, the template's available versions, whether the template
  takes post-generation actions, and whether the template is reproducible per FR-016.
- **FR-004**: The inspection description MUST have a **documented, stable shape** the
  agent skill can rely on (documented in prose with examples — not a machine-enforced
  schema). It is authored for the assistant to read, not for a separate program to
  validate against.
- **FR-004a**: Inspection MUST be safe to run against a source that has not been
  trusted: it MUST read only static template metadata (the template configuration and
  the cloned file listing) and MUST NOT render any template-controlled string,
  construct the engine's rendering environment, or load any template-declared
  extension — any of which can execute template-authored code. Consequently, question
  defaults (which may be template expressions) MUST be reported as their raw,
  un-rendered form and flagged as un-rendered. Inspection MUST NOT require trust.

**Inputs handoff (the phase-1 → phase-2 boundary)**

- **FR-005**: The deterministic phase MUST accept a single, self-contained inputs
  document, authored in phase 1, describing the source and version to use, the answer
  values to apply (including any bailiff-supplied values such as the generation date),
  and the trust decision for the run. The document MUST be a **documented plain-text
  format** (the engine's own answers/data-file shape wherever possible) that the
  assistant can author and a human can read.
- **FR-006**: Validation of the inputs MUST reuse the engine's own capabilities — a
  dry run and the engine's answer validation (FR-008) — rather than a bespoke
  re-implemented validator or a machine-enforced input schema. A malformed or
  incomplete inputs document MUST be caught (by that dry run) before any files are
  produced. (A typed/schema-validated handoff is explicitly NOT required for this
  slice and is introduced only if a non-assistant program ever consumes the handoff.)
- **FR-007**: The system MUST inject the current date as an ordinary answer value at
  generation time (so it is frozen into the recorded answers and replayed on
  reproduce), rather than relying on the template to read the clock.

**Validation & check mode**

- **FR-008**: The system MUST provide a check mode that validates an inputs document
  and reports problems without producing any files. For an action-taking template,
  the engine verifies trust before it validates answers; therefore check mode against
  an untrusted action-taking source legitimately reports the untrusted-source
  condition (a valid check result), and when a run is both untrusted and missing a
  required answer, the untrusted-source condition takes precedence in what is
  reported. Check mode MUST make this outcome explicit rather than appearing to
  validate answers it never reached.
- **FR-009**: The system MUST NOT re-implement the engine's own question validation;
  it MUST rely on the engine to validate answers and surface the results.
- **FR-010**: Every engine-surfaced input problem — including the
  missing-required-answer case (which the engine raises as a plain value error, not a
  typed engine error) — MUST be surfaced to the person or assistant with a clear,
  actionable message and a non-zero exit. Where a helper wraps the engine it MAY map
  these to its own error type; a bare recipe MAY surface the engine's own message and
  exit code directly. Either way the outcome MUST be legible, not a bare stack trace
  swallowed or shown without context.

**Generation (init)**

- **FR-011**: The system MUST generate a project from the inputs document
  non-interactively (it never prompts), applying the supplied answers at highest
  precedence and falling back to template defaults for anything not supplied.
- **FR-012**: A completed generation MUST record, in the generated project, the
  template source, the exact template version used, and the supplied answers, in a
  form that a later reproduce reads.
- **FR-012a**: The template source recorded in the generated project MUST be a
  fetchable location (the URL a later reproduce clones from), not a friendly display
  name, so that reproduce can resolve it with no catalog present.
- **FR-013**: Secret answers MUST NOT be written to the recorded answers, and internal
  dependency-ordering values MUST NOT be written to the recorded answers. Because the
  example template renders identity only (it carries no secret question and no
  dependency-ordering value), these two exclusions MUST be exercised by a dedicated
  throwaway test fixture template carrying one secret question and one hidden
  dependency-ordering value, so the guarantees are verified in this slice rather than
  merely asserted.
- **FR-014**: When the template provides an after-generation message, it MUST reach
  the person/assistant as post-step guidance. The engine already renders this message
  to its output stream during generation, so surfacing it is sufficient for this
  slice; capturing it as a separately-structured field is NOT required here (doing so
  would require the engine's deprecated surface, which this slice does not otherwise
  touch — deferred until a consumer needs the structured form).

**Reproducibility contract**

- **FR-015**: The system MUST provide a reproduce operation that regenerates a project
  from its recorded answers at the **recorded template version**, with no assistant or
  language-model step involved.
- **FR-015a**: Reproduce MUST overwrite the previously-rendered files in place and MUST
  NOT prompt for confirmation (non-interactive by invariant, per FR-011). Local edits
  to rendered files are therefore reverted to the template output; files the template
  marks write-once and files the template never renders are left untouched. Respecting
  local edits (a smart merge) is out of scope for this slice and belongs to the upgrade
  operation (roadmap spec 006). The SC-002 byte-comparison is performed on the
  in-place project tree after reproduce.
- **FR-016**: During inspection and before generation, the system MUST determine
  whether a template carries the mechanism required to record its own answers, and
  MUST refuse to generate from a template that does not, reporting it as not
  reproducible. This determination MUST be a **static** check of the fetched
  template's file listing (detecting the presence of the answer-recording file),
  consistent with the static-only rule of FR-004a — it MUST NOT render paths or build
  the engine environment.
- **FR-016a**: If a source exposes no version the engine can resolve as a valid
  release (the engine silently ignores tags it cannot parse as releases), the system
  MUST refuse with a structured error stating the source has no usable version, rather
  than proceeding against an unresolved source. (Enforcing one-git-repo = one-template
  more broadly, and rejecting mis-tagged multi-template repos, is deferred to the
  catalog spec — roadmap 002 — where multiple user-supplied sources are handled.)
- **FR-017**: The reproduce operation MUST NOT silently advance a project to a newer
  template version. Moving to a newer version MUST be a distinct, explicit,
  clearly-announced operation, which is out of scope for this slice.
- **FR-017a**: Faithful reproduce is only as immutable as the recorded version pin.
  When the recorded version is a movable label rather than an immutable revision, a
  re-published label can change reproduced bytes without error. This slice MUST
  document that limitation, and the template-author contract MUST treat published
  version labels as immutable. This slice does NOT record the immutable revision and
  does NOT add a label-moved check (deferred; see Clarifications 2026-07-09).
- **FR-018**: Post-generation actions declared by the template MUST run both at
  generation and at reproduce (so a reproduced project is complete), and the example
  template's action MUST be self-contained (require no network) **and produce no
  time- or environment-seeded bytes** (it initializes version control but creates no
  commit), so reproduce is hermetically byte-comparable per SC-002.

**Trust & consent**

- **FR-019**: The deterministic tool MUST NOT record trust on its own under any
  circumstances.
- **FR-020**: When a run requires trust that is absent, the system MUST refuse, take no
  destructive action, and report the exact source prefix that must be trusted, as a
  structured error.
- **FR-021**: The system MUST provide an explicit, separate consent action that records
  trust for a source prefix, and a way to list currently trusted sources.
- **FR-022**: Recorded trust MUST be stored in the exact form the tool uses to fetch the
  source, so that a subsequent run recognizes the source as trusted. Concretely, the
  tool MUST use fully-expanded canonical source URLs (never host shortcuts) for both
  fetching and trust storage, because the engine matches trust against the raw
  pre-expansion locator; a shortcut form and its expansion do not match each other.
- **FR-023**: Unattended runs (reproduce, continuous integration) MUST never prompt and
  MUST fail loudly when required trust is absent.
- **FR-023a**: Because an unattended reproduce of an action-taking template requires
  trust that the core will not provision, the system MUST document how such an
  environment obtains trust ahead of time (a pre-provisioned trust configuration the
  run reads), and the hermetic test setup MUST provision it that way rather than by
  prompting.
- **FR-023b**: Recording trust for a source prefix MUST be idempotent: recording a
  prefix already present leaves the trust configuration unchanged (no duplicate), and
  the operation MUST NOT corrupt or discard existing trust entries.

**Assistant procedure (phase 1)**

- **FR-024**: bailiff MUST ship an assistant-facing procedure (the skill — bailiff's
  primary deliverable) documenting how to inspect a template, present its questions and
  collect answer values, author a valid inputs document (referencing its documented
  format), explain the code-execution implication of trust and obtain consent before
  recording it, run the dry-run check and then generation, and hand off — establishing
  that the assistant authors inputs only and is never in the reproduce path.

**Engine coupling (cross-cutting, per constitution)**

- **FR-025**: The deterministic phase MUST prefer the engine's supported public
  surface — its command-line interface and public functions — and MUST prefer static
  parsing of the template configuration and file tree for inspection (which executes
  no template code). This slice MUST NOT use the engine's non-public internals at all;
  because static parsing suffices for the example template, NO containment adapter and
  NO internal-shape drift test are required here. IF a future need forces use of the
  engine's non-public internals, that use MUST be confined to a single containment
  point guarded by a drift test — but that is conditional, not a standing requirement
  of this slice.
- **FR-026**: The project MUST pin the engine to a compatible version range so its
  supported behavior cannot change under it without an explicit upgrade.

**Delivery hygiene in this slice**

- **FR-027**: The project's own documentation MUST be corrected wherever it
  contradicts the accepted model. At least three committed statements are known to be
  wrong and MUST be fixed: (a) the reproduce claim describing reproduce as a bare
  engine re-copy (which would silently advance the version) — correct it to the
  faithful, version-pinned reproduce this slice delivers; (b) the claim that
  rendering happens "without trust, so all action-taking stays in bailiff's
  orchestrator" — the accepted model is the opposite: action-taking is the template's
  own post-generation actions, run by the engine and gated by recorded trust, and
  bailiff never itself renders or executes template actions (Principle I); (c) the
  dependency-manifest comment asserting bailiff "never runs template actions (no
  trust)" — it contradicts FR-018 (actions run at generation and reproduce from a
  trusted source). All three MUST be corrected to the trusted-source-runs-actions
  model.

### Key Entities *(include if feature involves data)*

- **Template**: a single versioned source of scaffolding. Attributes relevant here:
  its source locator, its available versions, the questions it asks, its declared
  dependency-ordering values, whether it takes post-generation actions, and whether it
  can record its own answers (reproducibility).
- **Inputs document (run-spec)**: the phase-1 → phase-2 handoff. Names the source and
  version, the answer values (including the injected date), and the trust decision.
  Conforms to a published, versioned contract.
- **Inspection description (discover output)**: the machine-readable template
  description the assistant reads. Conforms to a published, versioned contract.
- **Recorded answers (in the generated project)**: the durable record of source,
  version, and supplied answers that makes a project reproducible; excludes secrets and
  internal ordering values.
- **Trust record**: the set of source prefixes a person has consented to run actions
  from, stored in the exact form used to fetch sources.
- **Example template ("bailiff-template-example")**: the concrete artifact under test — renders
  core project identity into README, license, ignore file, and standard directories;
  takes one self-contained post-generation action (initialize version control); carries
  the answer-recording mechanism; is published at a clean version. It intentionally
  combines several conceptual base modules into one template for this slice; it may be
  split apart in the project-setup port (roadmap spec 009). As a bailiff-authored
  template it MUST NOT use nondeterministic rendering (no clock/time or random
  filters); the current date reaches it only as the injected answer of FR-007.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a complete set of answers, a developer generates a project whose
  destination contains the rendered files, a recorded answers file naming the template
  and its exact version, and an initialized version-control repository — in a single
  generation run with no manual editing.
- **SC-002**: Reproducing a generated project from its recorded answers yields a file
  tree **byte-identical** to the first render, compared over an explicitly enumerated
  path set, on a machine and in continuous integration, with no assistant involved.
  For the example template the comparison covers every rendered file and the recorded
  answers file, and the excluded-path allowlist is **empty** — the example template's
  post-generation action initializes version control **without creating a commit**, so
  it introduces no time- or environment-seeded bytes. Any future template whose action
  produces non-deterministic bytes MUST enumerate exactly which paths are excluded; a
  bare "external state" exclusion is not permitted as a success criterion.
- **SC-003**: Reproduce always uses the version recorded in the project and never a
  newer one; a project generated at a given template version reproduces at that same
  version 100% of the time.
- **SC-004**: Attempting to generate an action-taking template from an untrusted source
  refuses 100% of the time with a message naming the exact prefix to trust, and takes no
  destructive action; after consent is recorded, the same generation succeeds.
- **SC-005**: Attempting to generate from a template that cannot record its answers is
  refused 100% of the time, with nothing produced.
- **SC-006**: Every input problem the person or assistant sees is a typed, structured
  bailiff error; no raw engine stack trace reaches them for the covered cases (missing
  required answer, untrusted source, non-reproducible template).
- **SC-007**: The whole mechanical loop (inspect, check, generate, reproduce, trust
  refusal) is demonstrable and testable without any assistant or language model, and —
  except one clearly-marked live-source smoke check — runs without network access.
- **SC-008**: An incomplete or malformed inputs document is caught by the engine's own
  dry run before any files are produced — no bespoke input-schema validator is needed
  or present; the dry run is the gate.
- **SC-009**: The deterministic phase uses no engine internals in this slice (inspection
  is a static parse), so there is no containment adapter to drift; a test asserts
  inspection executes no template code and requires no trust.
- **SC-010**: The generation date is frozen at generation time and replayed on
  reproduce: a project generated on one date and reproduced on a later date renders
  the original date, not the reproduce-day date, 100% of the time.
- **SC-011**: When the example template provides an after-generation message, the
  captured structured field contains the message with answer values resolved (no
  unresolved placeholders remain).
- **SC-012**: For a fixture template carrying a secret question and a hidden
  dependency-ordering value, neither the secret value nor the ordering value appears
  in the recorded answers after generation.

## Assumptions

- **Single template, single source, single generation.** This slice covers exactly one
  template in one source, generated with one render and reproduced faithfully. Multiple
  sources, a browsable catalog, selecting among many templates, and dependency-ordered
  multi-template runs are out of scope (later roadmap specs 002 and 003).
- **Report-all-gaps is deferred.** When required answers are missing, this slice reports
  at least the first, relying on the engine's own validation. Collating *every* missing
  answer across *all* enabled templates in one pass is a deliberate later extension
  (roadmap spec 003); the check-mode seam is designed so that extension fits without
  redesign.
- **Global per-run defaults are out of scope.** Pre-filling answers from a user-level
  configuration is a later roadmap spec (004). In this slice every applied answer comes
  from the inputs document (or a template default).
- **Secrets handling is minimal here.** Inspection reports which questions are secret and
  the recorded answers exclude secrets, but fetching secret values from an external store
  is a later roadmap spec (005). This slice does not require a secret-bearing example.
- **Upgrading to a newer template version is out of scope.** Reproduce is version-faithful
  only; the explicit upgrade/migration operation is a later roadmap spec (006).
- **The example template is disposable.** "bailiff-template-example" is hand-published for this
  slice (the automated authoring-and-distribution pipeline is a later roadmap spec, 008)
  and may be recreated or split later.
- **The person consents to trust out-of-band.** bailiff explains the implication and records
  the decision, but the decision itself is the human's; bailiff never decides to trust.
- **Reproduce is process-deterministic, not necessarily byte-identical in the world.**
  Post-generation actions may touch state outside the render; byte comparison for the
  determinism check excludes such externally-sourced state.
- **The engine is the copier scaffolding engine, used as a pinned dependency and driven
  primarily through its command-line interface.** bailiff delegates all rendering, answer
  recording, version pinning, and the reproduce cycle to it, and drives it only through
  its supported public surface (its CLI / public functions), inspecting templates by
  static configuration parsing. This slice touches none of the engine's non-public
  internals.
- **bailiff is a skill + a template + minimal glue, not a published application.** The
  deliverables are the assistant procedure, the example template, and the small
  deterministic helper(s)/recipes that do only what the engine's CLI and the assistant
  cannot do directly. No standalone tool is published for this slice.
