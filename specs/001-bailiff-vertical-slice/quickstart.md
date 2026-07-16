# Quickstart — bailiff vertical slice (001)

End-to-end validation of the whole loop: **discover → trust → init → reproduce**,
against the bundled `examples/bailiff-template-example` template. Matches the automated
tests and `scripts/try-bailiff.sh`.

## Prerequisites

- `git`, [`uv`](https://docs.astral.sh/uv/), and `gh` authenticated
  (`gh auth status`) — the example template's LICENSE task calls `gh api`.
- From the repo root: `uv sync`.

## The fast path

```sh
bash scripts/try-bailiff.sh          # walks every step below, pausing to inspect
bash scripts/try-bailiff.sh --no-pause
KEEP=1 bash scripts/try-bailiff.sh   # keep the scratch workspace to poke around
```

## The manual path

### 0. A real template repo to point at

`bailiff-template-example` isn't published yet, so make a local tagged repo from the
bundled example (copier treats a local path exactly like a remote):

```sh
TPL=$(mktemp -d)/bailiff-template-example
cp -R examples/bailiff-template-example "$TPL"
git -C "$TPL" init -q && git -C "$TPL" add -A \
  && git -C "$TPL" commit -qm base && git -C "$TPL" tag v1.0.0

WORK=$(mktemp -d)
export COPIER_SETTINGS_PATH="$WORK/settings.yml"   # isolate trust from your real config
```

### 1. Discover (no trust needed)

```sh
uv run bailiff discover "$TPL"
```

Expect JSON with `"reproducible": true`, `"has_tasks": true`, the five questions,
and `"versions": ["v1.0.0"]`.

### 2. Trust (the template runs tasks → consent required)

```sh
uv run bailiff trust add "$TPL"    # try init first without this to see the exit-3 refusal
uv run bailiff trust list
```

### 3. Init — dry-run, then real

```sh
cat > "$WORK/run-spec.yml" <<EOF
source: "$TPL"
dest: "$WORK/my-project"
answers: { project_name: hello, org: acme, license: MIT, description: my project }
EOF

uv run bailiff init --run-spec "$WORK/run-spec.yml" --check   # writes nothing
uv run bailiff init --run-spec "$WORK/run-spec.yml"           # generates

cat "$WORK/my-project/.copier-answers.yml"   # note _src_path + _commit: v1.0.0
```

Expect a rendered `README.md`, a `gh`-generated `LICENSE`, `.gitignore`,
`src/.gitkeep`, a `justfile`, and an initialized `.git`.

### 4. Reproduce — faithful, agent-free

```sh
echo "CORRUPTED" > "$WORK/my-project/README.md"
( cd "$WORK/my-project" && uv run --project "$OLDPWD" bailiff reproduce . )
cat "$WORK/my-project/README.md"    # restored config-consistent at v1.0.0
```

Copier-rendered files revert to their recorded bytes. (LICENSE is a task side
effect sourced from GitHub's live database, not pinned to the commit, so — like
`.git` — it is outside the config-consistent reproduce set.)

## What this proves

- **US3** discover is static + safe (no code, no trust).
- **US4** action-taking source is refused until trusted, then unblocked by consent.
- **US1** init records `_src_path`/`_commit`/answers; `today` is frozen.
- **US2** reproduce is config-consistent at the recorded commit, no agent.
- **US6** `--check` validates and writes nothing.

## The full offline suite

```sh
uv run pytest -q            # 35 hermetic tests (local git fixtures, no network)
uv run pytest -m network    # the one live smoke test (skips until bailiff-template-example is published)
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy
```
