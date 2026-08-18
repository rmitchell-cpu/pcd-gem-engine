---
type: sop
title: pcd-gem-engine — Repository Guide for AI Assistants
date: 17 August 2026
description: Orientation and working conventions for the PCD Concierge pipeline codebase — architecture, commands, naming authority, and the known drift traps an assistant must not walk into.
tags:
  - pcd-gem-engine
  - concierge-pipeline
  - developer-guide
  - conventions
---

# CLAUDE.md — pcd-gem-engine

Guidance for Claude Code (and any AI assistant) working in this repository.

## What this repo is

The **PCD Concierge Workflow Engine**: a Python pipeline that takes a GP (General
Partner) fund manager pitch deck as a PDF and produces a set of schema-validated
JSON artifacts — a prescreen score, a deck analysis, an LP framing brief, database
taxonomy tags, an LP tear sheet, and four LP outreach email variants — plus two
LLM evaluators, a review bundle, a FastAPI review dashboard, and a Word-document
renderer for the customer-facing deliverable.

Every analytical stage is a Claude API call whose prompt lives in `prompts/` and
whose output is validated against a Pydantic model in `src/models.py`. There is no
business logic inside the stages; the code is the harness (sequencing, retries,
validation, persistence) and the prompts are the product.

A second, independent tool lives in `hubspot_snapshot/` — a standalone
HubSpot marketing-email reporting generator that shares nothing with the pipeline
but the repository. See `hubspot_snapshot/README.md`.

## Naming authority — read this before renaming anything

`pcd-vocabulary-canonical.md` in the project root is the **single source of truth**
for stage names, tier labels, class names, table names, and retired terminology.
Consult it before introducing or changing any identifier, and update it in the same
session as any change that affects vocabulary.

Retired vocabulary that must not be reintroduced: `GEM 1`–`GEM 5`, `Gatekeeper` (as
a stage name), `Tourist` (as a tier), `Randy Eval`, `CrossGEMEval`, `gem_jobs` /
`gem_artifacts` / `gem_status_log`, `gatekeeper_score` / `gatekeeper_class`.

Persona names (Steph, Ted, Sam, Randy, JSON John) are still fine in prose and
prompt text, but never as stage names, class names, file names, or schema fields.

## Environment setup

`requires-python >= 3.9`. The repository is developed against a project-local venv
at `.venv/`, which is **gitignored and absent from a fresh clone** — create it
before running anything:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev,web]"
```

Always invoke the interpreter as `./.venv/bin/python`, never bare `python` or
`python3`. This is deliberate: a Homebrew Python 3.14 shadowing incident on
2 July 2026 broke every bare-interpreter invocation, and the slash commands in
`commands/` were rewritten to the explicit venv path in response (commit
`f399735`). `.venv-314-freeze-2026-07-24.txt` preserves the 3.14-era pinned
dependency set for reference; it is not an install target.

Credentials go in `.env` at the project root (copy `.env.example`):

| Variable | Consumer | Required for |
|---|---|---|
| `ANTHROPIC_API_KEY` | `src/stage_runner.py` | every pipeline stage |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | `src/supabase_client.py` | pipeline writes |
| `SUPABASE_ANON_KEY` | `src/supabase_client.py` | dashboard reads |
| `DATABASE_URL` | `migrate.py` | migrations (**not** in `.env.example`) |
| `HUBSPOT_TOKEN` | `hubspot_snapshot/client.py` | HubSpot snapshot only |

Supabase is optional at runtime: every write helper in `src/persistence.py` is
wrapped in a `try/except` that prints a warning and continues, so the pipeline runs
fully on the filesystem alone.

## Common commands

```bash
# Full pipeline on a deck
./.venv/bin/python run.py path/to/deck.pdf

# Rerun a single stage against persisted upstream artifacts
./.venv/bin/python run.py --stage 04_preqin_taxonomy --job 20260426_134003_ee830c53

# Inspect jobs
./.venv/bin/python run.py --list-jobs
./.venv/bin/python run.py --status --job <job_id>

# Tests (offline — no API key needed; schema + HubSpot math only)
./.venv/bin/python -m pytest tests/ -v

# Review dashboard (needs the [web] extra)
./.venv/bin/python web_server.py --port 8000

# Word deliverable from a completed job
./.venv/bin/python render_pipeline_report.py --artifacts-dir jobs/<job_id>/artifacts --validate-only
./.venv/bin/python render_pipeline_report.py --artifacts-dir jobs/<job_id>/artifacts --output ~/Desktop/Pipeline_Report.docx

# Database migration — dry run first, always
./.venv/bin/python migrate.py --dry-run

# HubSpot snapshot (offline fixture mode)
./.venv/bin/python -m hubspot_snapshot --fixture tests/fixtures/hubspot_sample.json
```

There is no linter, formatter, or CI configuration in the repo. Match the style of
the file you are editing.

## Pipeline architecture

### Stage sequence

`src/orchestrator.py:run_pipeline()` is the one authoritative execution path:

```
deck.pdf
  └─ ingestion (PyMuPDF)          → artifacts/parsed_deck.json
     └─ prescreen                 → prescreen.json          [GATE]
        ├─ challenging (<20/40)    → hard stop, internal-only bundle
        └─ 01_fund_extract        → 01_fund_extract.json    [fail-soft]
           └─ 02_deck_analysis    → 02_deck_analysis.json
              ├─ 03_angle_brief   → 03_angle_brief.json
              ├─ 04_preqin_taxonomy → 04_preqin_taxonomy.json
              ├─ 05_deal_card     → 05_deal_card.json
              └─ 06_lp_emails     → 06_lp_emails.json
                 ├─ eval_voice        → eval_voice.json
                 └─ eval_cross_stage  → eval_cross_stage.json
                    └─ regeneration loop (≤2) → review_bundle.json
```

Two routing behaviors matter:

- **The prescreen is a gate.** A `challenging` classification stops the run before
  any LP-facing artifact is generated, saves a minimal bundle, and sets state
  `rejected_challenging`. Do not add code paths that generate LP content for a
  challenging GP.
- **`01_fund_extract` is fail-soft.** If it errors, the orchestrator logs the
  failure, prints a warning, and continues without it. Every downstream consumer
  (renderer, dashboard, bundle) treats it as optional, because jobs run before
  24 July 2026 do not have it.

### Stage execution protocol

Every stage goes through `src/stage_runner.py:run_stage(stage_name, job_id, context)`,
which does the same seven things each time:

1. Load `prompts/<stage_name>.md` and hash it (`prompt_hash`, first 12 hex chars of
   SHA-256) for artifact provenance.
2. Use the prompt as the **system** message; assemble the **user** message by
   wrapping each `context` dict entry in pseudo-XML tags (`<deck_text>…</deck_text>`).
3. Append a JSON-only output instruction if the stage appears in
   `STAGE_SCHEMA_MAP`.
4. Call `client.messages.create` with `MODEL` and `MAX_TOKENS` from
   `config/settings.py`. Note: no `temperature` — it was removed in commit
   `02193f7` because Opus 4.7 rejects it with HTTP 400. Do not reintroduce it.
5. Extract JSON tolerantly (`_extract_json` strips code fences and brace-matches).
6. Validate against the stage's Pydantic model; on `ValidationError`, retry up to
   `MAX_STAGE_RETRIES` (2) with the validation failure summary fed back to the model
   as a retry note. Rate limits get a separate 30s/60s/90s backoff.
7. Persist via `save_artifact` and return a `StageResult` carrying model version,
   prompt hash, token usage, and retry count.

To add a stage: write `prompts/<name>.md`, add the Pydantic model to
`src/models.py`, register it in `STAGE_SCHEMA_MAP` (`src/validator.py`), add the
name to `PIPELINE_STAGES` (`config/settings.py`), wire the call into
`run_pipeline`, add its context assembly to `rerun_stage`, and add a `WorkflowState`
member for its completion.

### Truth hierarchy and regeneration

`config/settings.py` splits stages into two frozen sets, and this split is a
correctness invariant, not a style preference:

- `UPSTREAM_TRUTH_STAGES` — `prescreen`, `01_fund_extract`, `02_deck_analysis`,
  `03_angle_brief`. **Immutable.** Never regenerated, never repaired.
- `DOWNSTREAM_REPAIRABLE_STAGES` — `04_preqin_taxonomy`, `05_deal_card`,
  `06_lp_emails`. Regeneratable with evaluator feedback injected as a system
  suffix, up to `MAX_REGENERATION_ATTEMPTS` (2).

When an evaluator returns `decision: revise`, the orchestrator repairs only the
flagged downstream artifacts, then re-runs both evaluators. If they still fail
after two rounds the run completes anyway with `flagged_items` set on the bundle
and the state left at `human_review_pending` — a human always closes the loop.

### Persistence

Dual-write, filesystem-first (`src/persistence.py`):

```
jobs/<job_id>/                    # job_id = YYYYMMDD_HHMMSS_<8 hex>
  manifest.json                   # JobManifest — current state, fund name
  review_bundle.json              # ReviewBundleManifest — final summary
  deck/<original>.pdf
  artifacts/<stage>.json
  logs/status_log.jsonl           # append-only StatusLogEntry per transition
```

`jobs/` is gitignored — it is a local cache, and Supabase (`pipeline_jobs`,
`pipeline_artifacts`, `pipeline_status_log`, `gp_pipeline`, plus the `gp_decks`
storage bucket) is the central record. The dashboard reads Supabase and falls back
to the filesystem when credentials are absent.

`WorkflowState` (`src/models.py`) is the state machine; every transition goes
through `log_transition` + `update_state` so the JSONL log and the Supabase log
stay in step.

## Repository map

| Path | Role |
|---|---|
| `run.py` | pipeline CLI — full run, single-stage rerun, list, status |
| `web_server.py` → `web/app.py` | FastAPI review dashboard + Jinja templates |
| `render_pipeline_report.py` | artifacts → `Pipeline_Report.docx` CLI |
| `migrate.py` | applies `migrations/001_schema.sql` |
| `config/settings.py` | paths, model, stage order, truth hierarchy, formatting rules |
| `src/orchestrator.py` | **the** pipeline — sequencing, routing, regeneration, bundle |
| `src/stage_runner.py` | shared LLM call/validate/persist harness |
| `src/models.py` | all Pydantic artifact models + `WorkflowState` |
| `src/validator.py` | `STAGE_SCHEMA_MAP` — stage name → model |
| `src/persistence.py` | job lifecycle, artifact I/O, Supabase dual-write |
| `src/ingestion.py` | PDF text extraction (PyMuPDF) |
| `src/rendering/` | `python-docx` report renderer (`styles.py`, `formatters.py`, `io.py`, `sections/`) |
| `prompts/*.md` | one system prompt per stage; `references/preqin_taxonomy.md` is injected into stage 04 |
| `schemas/*.json` | exported JSON Schema for the Pydantic models — **documentation only, not loaded at runtime** |
| `migrations/` | `001` is the original `gem_*` schema; `002` documents the live `pipeline_*` rebuild |
| `commands/*.md` | Claude Code slash commands, published via `.claude-plugin/plugin.json` |
| `SKILL.md` | the `pipeline-report-renderer` skill wrapping `render_pipeline_report.py` |
| `hubspot_snapshot/` | independent HubSpot email reporting tool |
| `tests/` | offline pytest suite — schema validation + HubSpot metric math |

## Output conventions (PCD house style)

These are enforced at render time in `src/rendering/formatters.py` and asserted in
`SKILL.md`. Preserve them in any generated prose or document output.

- **Currency:** `US$` with a single `M`/`B` suffix — `US$70-75M`, never `$70MM`,
  `USD 70 million`, or `U.S.$`.
- **Dates:** `dd Month yyyy`. ALL CAPS in structural positions (header strips,
  metadata strips, "as of" lines): `27 APRIL 2026`. Mixed case in prose:
  `27 April 2026`. Pipeline artifacts emit the space-separated `DD MM YYYY` form,
  which `parse_pipeline_date` converts.
- **Tier display:** `Native`, `High-Potential Aspiring`, `Challenging`.
- **Missing data sentinels:** `[Information Not Available in Deck]` (deck-analysis
  convention) and `[Data Not Disclosed]` (deal-card convention). Pass them through
  unchanged; never substitute a guess.
- **No PCD branding in LP-facing content.** Stage 06's invariant is that Randy's
  affiliation with PCD is invisible in LP emails. Do not add it.

Documents, plans, and summaries produced *about* this repo follow Open Knowledge
Format v0.1 — YAML frontmatter (`type`, `title`, `date`, `description`, `tags`)
followed by Markdown, with a `## Related Context` section of bracketed links. This
file is an example.

## Known drift and traps

These are real, verified inconsistencies in the current tree. Do not "fix" them
silently as a side effect of other work, and do not be misled by them.

1. **`src/stages/*.py`, `src/evaluators.py`, `src/regeneration.py`, and
   `src/bundle.py:assemble_review_bundle()` are dead code.** Nothing imports them;
   `run_pipeline` inlines all of that logic itself. Editing
   `src/stages/05_deal_card.py` changes nothing at runtime. Real behavior lives in
   `src/orchestrator.py`. (The digit-prefixed module names are not importable as
   Python identifiers anyway, which is part of why they were abandoned.) The one
   thing `src/stages/` is still good for: `commands/rerun-stage.md` cites it as the
   list of valid stage names.
2. **Fixed 17 August 2026 — `migrate.py` now runs `002_rebuild_schema.sql`,** the
   pipeline_* schema of record; until then it ran `001_schema.sql` and a live run
   would have recreated the retired `gem_*` tables. What remains true: 001 is
   history only — never point the script back at it. 002 is safe to re-run against
   production (all `CREATE TABLE IF NOT EXISTS`; the column renames it documents
   were applied by hand and exist only as comments) but is NOT a fresh-database
   bootstrap — it references `gp_pipeline(id)`, which only 001 created, and fails
   loudly on an empty database. Still confirm with the user before any non-dry-run
   migration.
3. **Model constant drift.** `config/settings.py` hardcodes
   `MODEL = "claude-opus-4-7"`; `.env.example` advertises a `GEM_MODEL` override
   defaulting to `claude-opus-4-6`. `GEM_MODEL` is never read by any code. Changing
   the model means editing `config/settings.py`.
   Note also that both names are a generation behind the current Claude 5 family
   (`claude-opus-5`, `claude-sonnet-5`), so every stage runs on the older model.
   That is the one trap here with live output consequences, and the fix is a
   one-line change — but make it a deliberate decision, not a drive-by edit: the
   stage prompts and their schema validators were tuned against the pinned model,
   so an upgrade needs a pipeline run on a known deck and a diff of the artifacts
   before it is trusted. Re-check the current model lineup at the time of reading
   rather than treating this list of names as durable.
4. **Fixed 17 August 2026 — kept for the pattern.** `commands/dashboard.md` and
   `commands/migrate.md` carried a doubled interpreter path
   (`./.venv/bin/./.venv/bin/python`) from the venv-path rewrite; both now read
   `./.venv/bin/python`. If a command file ever fails with "no such file or
   directory" on the interpreter, check for this doubling before anything else —
   a bulk path rewrite can reintroduce it in one edit.
5. **`SKILL.md` contradicts itself on where this repo lives.** Line 19 gives the
   job-artifact path under a retired layout (`~/Desktop/Claude Concierge/…`) while
   line 77 already carries the correct current one
   (`~/Desktop/CLAUDE/02-Internal-Operations/Concierge-Service/pcd-gem-engine`).
   Trust line 77, and resolve job paths relative to the repository root rather than
   either literal. The `~/Desktop/Pipeline_Report.docx` paths elsewhere in that file
   are output destinations a user chooses, not layout assertions — leave them alone.
6. **`src/stages/05_deal_card.py` and `06_lp_emails.py` carry `TODO` comments about
   loading `01_fund_extract` for ground truth.** That wiring is still open in the
   live orchestrator too — stages 05 and 06 do not receive the fund extract, in
   either the full-pipeline path or the single-stage rerun path. What is missing is
   DIRECT access, not the facts themselves: the extract is injected into
   `02_deck_analysis` (`src/orchestrator.py:189`), so it reaches 05 and 06
   second-hand through `analyst_extraction_report`. Read a verified-facts
   discrepancy in a deal card or an LP email as a lossy hand-off, not as the
   extract having been ignored.

## Git workflow

Commit messages in this repo are descriptive and explain the *why*, often naming
the punchlist item or the incident that motivated the change (`requires-python
>=3.9: venv rebuilt on CLT python (brew-immune)`). Match that register. Never
commit `.env`, `jobs/`, `.venv/`, or generated `artifacts/`.

## Related Context

- [pcd-vocabulary-canonical.md] — canonical stage, tier, and class naming authority
- [SKILL.md] — `pipeline-report-renderer` skill contract and report layout
- [hubspot_snapshot/README.md] — HubSpot snapshot tool, rate definitions, verification
- [migrations/002_rebuild_schema.sql] — live Supabase schema of record
- [Meridian Export Collective]
- [Capital Mobilization]
- [HubSpot CRM]
