---
name: pipeline-report-renderer
description: Render pcd-gem-engine pipeline job artifacts into a professionally formatted Word document. Reads the eight JSON artifacts produced by a completed pipeline run from jobs/<job_id>/artifacts/ and produces a Pipeline Report.docx matching the institutional layout of the legacy 650 Fund II report (cover page with prescreen score and stage-completion icons, Step 1 Prescreen Intake Report, Step 2 Deck Analysis Report, Step 3 LP Email Variants with internal Angle Brief, Step 4 Preqin Taxonomy Translation, Step 5 Deal Card tear sheet, optional Appendix with Voice and Cross-Stage Evaluation). Use this skill whenever the user says "render the pipeline report", "build the Word doc from the artifacts", "produce the GP Concierge pipeline report", "generate Pipeline_Report.docx", or any variant referring to converting a pcd-gem-engine job folder into a customer-facing or internal Word document. Also trigger when the user mentions a job_id (a folder name like 20260426_134003_ee830c53) and asks for a Word output, or when the user has just completed a pipeline run and wants the report deliverable.
---

# Pipeline Report Renderer — DOCX Synthesis Layer

This skill is a thin wrapper around the Python renderer at `pcd-gem-engine/render_pipeline_report.py`. It reads structured JSON artifacts from a completed pipeline job and produces a single Word document covering the cover page, five analytical steps, and an optional internal-use Appendix.

The skill delegates rendering to the Python script — it does not reimplement the document layout. Visual fidelity, formatting normalization, and section composition are all owned by the script and its modules in `pcd-gem-engine/src/rendering/`.

---

## Required Inputs

The user must specify (or the assistant must determine) the path to a job's artifacts directory. The path is typically:

```
~/Desktop/Claude Concierge/pcd-gem-engine/jobs/<job_id>/artifacts/
```

Where `<job_id>` is a folder name like `20260426_134003_ee830c53`.

The artifacts directory must contain six **REQUIRED** files. The renderer will fail if any are missing:

- `prescreen.json` — Stage 0 prescreen scoring and verdict
- `02_deck_analysis.json` — Stage 2 structured deck extraction
- `03_angle_brief.json` — Stage 3 LP framing strategy
- `04_preqin_taxonomy.json` — Stage 4 database translation
- `05_deal_card.json` — Stage 5 LP tear sheet
- `06_lp_emails.json` — Stage 6 four LP email variants

Three additional **OPTIONAL** files render into the document if present:

- `01_fund_extract.json` — Stage 1 fund terms extract (JSON John; implemented 24 July 2026 — optional because jobs run before that date do not have it)
- `eval_voice.json` — Voice Evaluator output (renders into Appendix)
- `eval_cross_stage.json` — Cross-Stage Consistency Evaluator output (renders into Appendix)

One file is **NEVER RENDERED** — it exists in job folders for other downstream uses but is intentionally excluded from the report:

- `parsed_deck.json` — raw deck text used as pipeline input

---

## Strict Operational Constraints

The renderer applies these rules at render time. They are non-negotiable PCD house style.

- **Currency normalization:** all currency tokens normalized to `US$` form with `M` (millions) or `B` (billions) suffix. The renderer rewrites `$70-75MM`, `USD 70 million`, and similar variants to `US$70-75M` automatically in deal-card prose. Other sections preserve upstream formatting.
- **Date casing:** all-caps `27 APRIL 2026` in structural positions (page header strip, metadata strips, "as of" lines). Mixed-case `27 April 2026` in prose contexts (cover-page date line, etc.).
- **Tier vocabulary:** prescreen classifications display as `Native`, `High-Potential Aspiring`, or `Challenging`. The retired term "Tourist" is not used.
- **Persona names retired from system identifiers:** the rendered document uses functional stage names (Step 1 Prescreen, Step 5 Deal Card) — not Gatekeeper, Sam, Steph, Ted. Person names remain acceptable in informal references but never as section headings.
- **Missing-data sentinels:** sections handle absent data using `[Information Not Available in Deck]` (deck-analysis stage convention) or `[Data Not Disclosed]` (deal-card stage convention) — both preserved as-is when present in the artifacts.
- **No agency branding in LP-facing content:** the rendered emails honor Stage 06's invariant that Randy's affiliation with PCD is invisible in LP communications.

---

## Invocation

The renderer is a Python script that runs from the project root.

Use the engine's own venv interpreter (`./.venv/bin/python`) — it carries
`python-docx`; the system `python3` does not.

**From a Cowork sandbox** with project filesystem mounted:

```bash
cd /path/to/pcd-gem-engine
./.venv/bin/python render_pipeline_report.py \
    --artifacts-dir jobs/<job_id>/artifacts \
    --output ~/Desktop/Pipeline_Report.docx
```

**From a local Mac terminal:**

```bash
cd ~/Desktop/CLAUDE/02-Internal-Operations/Concierge-Service/pcd-gem-engine
./.venv/bin/python render_pipeline_report.py \
    --artifacts-dir jobs/<job_id>/artifacts \
    --output ~/Desktop/Pipeline_Report.docx
```

**Validate artifacts without rendering:**

```bash
./.venv/bin/python render_pipeline_report.py \
    --artifacts-dir jobs/<job_id>/artifacts \
    --validate-only
```

**Suppress the eval Appendix:**

```bash
./.venv/bin/python render_pipeline_report.py \
    --artifacts-dir jobs/<job_id>/artifacts \
    --output ~/Desktop/Pipeline_Report.docx \
    --no-evals
```

If the user has Word open with a previously rendered version, force-quit Word before re-rendering — Word caches the file and may show a stale version after re-render:

```bash
osascript -e 'tell application "Microsoft Word" to quit'
```

---

## Output Format

The rendered Word document follows this section structure in order:

```
PAGE 1            Cover Page
                    Header strip (PCD GP CONCIERGE PIPELINE REPORT — <fund> — <date>)
                    Title (GP CONCIERGE PIPELINE REPORT)
                    Subtitle (fund name, orange)
                    Horizontal rule
                    Prepared-by + date
                    PIPELINE STATUS callout (prescreen score + tier)
                    Step-icon row (✓ for stages with artifacts present)
                    Footer (PCD — Confidential — Page N)

PAGES 2-3         STEP 1 — PRESCREEN INTAKE REPORT
                    Metadata strip
                    1. Scoring Assessment (4-pillar scoring table)
                    Pillar Diagnostics banner
                    Pillar 1-4 subsections with diagnostic prose
                    Verdict callout (tier + intervention detail)
                    2. Gap Analysis & Recommended Next Steps

PAGES 4-10        STEP 2 — DECK ANALYSIS REPORT
                    Executive Summary callout
                    Section 1 — Market & Focus
                    Section 2 — The Opportunity
                    Section 3 — The Right Now Argument
                    Section 4 — Sourcing Forensics
                    Section 5 — Track Record Assessment
                    Section 6 — Logic & Discipline (3-row table)
                    Section 7 — Red Flags
                    Questions for the GP (bulleted list)
                    Information Gaps (bulleted list)

PAGES 11-13       STEP 3 — LP EMAIL VARIANTS
                    Email A (Fit / Relevance) — angle banner, subjects, body callout
                    Email B (Differentiated Edge) — same structure
                    Email C (Proof / Repeatability) — same structure
                    Email D (Short Forwardable) — same structure
                    Angle Brief — Internal PCD Use Only subsection

PAGES 14-16       STEP 4 — PREQIN TAXONOMY TRANSLATION
                    1. Strategy Summary in Plain English
                    2. Translation Matrix (5-column table)
                    3. Search Strategy Checklist (Verticals, Industries, Keywords)
                    4. Boolean Search Strings (3 callouts)
                    Canonical Strategy Tags footer

PAGES 17-19       STEP 5 — DEAL CARD
                    Dark-navy fund-name header callout (visual signature)
                    The Right Now Window
                    Sourcing Forensics
                    Logic & Discipline (3-row table)
                    Track Record & Key Terms
                    Action CTA
                    INTERNAL NOTE — PCD Use Only

PAGES 20+         APPENDIX — PIPELINE EVALUATION (default on)
                    Voice Evaluation (per-email scores + decision)
                    Cross-Stage Consistency Evaluation (six-check status)
```

Page count totals approximately 19-22 pages depending on artifact prose density.

---

## Pipeline Position

This skill is the final, customer-facing layer of the GP Concierge pipeline:

```
PDF deck → parsed_deck.json → 02_deck_analysis → 03_angle_brief → 04_preqin_taxonomy
                            → 05_deal_card → 06_lp_emails → eval_voice + eval_cross_stage
                            → [pipeline-report-renderer] → Pipeline_Report.docx
```

The renderer reads only the JSON artifacts. It does not call the LLM, does not re-process the deck, and does not modify any upstream artifact. Its sole responsibility is composition and presentation.

The Word document lands at the path the user specifies via `--output`. The convention is `01-Pipeline/<deck-version>/Pipeline_Report.docx` inside each GP project folder, but any path is accepted.

---

## Failure Modes and How to Handle Them

- **Missing required artifact:** the script exits with a clear error message naming the missing files. Resolution: re-run the relevant pipeline stage.
- **Malformed JSON:** the loader returns `None`; the affected section renders a `[Stage Not Run — Artifact Not Available]` placeholder rather than aborting.
- **Word displaying a stale version after re-render:** force-quit Word with `osascript -e 'tell application "Microsoft Word" to quit'`, then re-open the file. The render itself succeeded; Word's file cache is the issue.
- **Validation warning about `zoom` element:** benign python-docx default; Word ignores it. Not a real error.
- **Stage 1 artifact absent:** expected for jobs run before 24 July 2026, when `01_fund_extract` (JSON John) was implemented. Treated as optional; the fund-extract data simply does not render for those jobs.

---

## Related Skills and Documentation

- `pcd-vocabulary-canonical.md` (in the project root) — single source of truth for stage names, tier labels, and retired vocabulary
- The legacy 650 Fund II Pipeline Report — visual reference for the rendered layout
- The pcd-gem-engine source tree at `src/rendering/` — implementation details if the renderer needs modification
