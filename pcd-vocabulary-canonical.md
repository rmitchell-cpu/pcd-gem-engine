---
type: concept
title: PCD Concierge Pipeline — Canonical Vocabulary
date: 24 July 2026
description: Single source of truth for pcd-gem-engine pipeline vocabulary — canonical stage names, tier labels, and retired terminology.
tags: [pcd-gem-engine, concierge-pipeline, vocabulary, naming]
---

# PCD Concierge Pipeline — Canonical Vocabulary

**Effective date:** 26 April 2026 (rename pass complete; pipeline verified end-to-end). **Last updated:** 24 July 2026 (item 6: `01_fund_extract` implemented).
**Maintained by:** Randy C. Mitchell, PCD
**Authority:** This document is the single source of truth for Concierge pipeline vocabulary. Documents that conflict with this lookup should be updated to match.

---

## Purpose

When auditing or writing new content related to the GP Concierge pipeline, use this lookup to verify vocabulary is current. Anything in the "Retired Names" columns is no longer canonical and should be updated when found.

To use this with Cowork: paste the contents of this file into a Cowork prompt and ask Cowork to "audit the attached document against this canonical vocabulary list and propose updates."

---

## Pipeline stages (in execution order)

| Stage Number | Canonical Name | Retired Names |
|---|---|---|
| 0 (entry) | `prescreen` | "Gatekeeper Intake," "Step 1 — Gatekeeper" |
| 1 | `01_fund_extract` (implemented 24 July 2026; fail-soft — pipeline continues if it errors) | "JSON John" (still acceptable as informal name) |
| 2 | `02_deck_analysis` | "GEM 2 Extractor," "Step 2 — Deck Analyst Extractor," "GP Deck Analyst" |
| 3 | `03_angle_brief` | "Angle Brief" (was already this name; no change) |
| 4 | `04_preqin_taxonomy` | "Step 4 — Taxonomy Ted," "Taxonomy Ted Translation Matrix" |
| 5 | `05_deal_card` | "Step 5 — Summary Sam," "Summary Sam Deal Card," "Tear Sheet" |
| 6 | `06_lp_emails` | "GEM 3," "Step 3 — Steph LP Email Variants," "Steph emails" |

---

## Evaluators

| Canonical Name | Retired Name |
|---|---|
| Voice Evaluator (`eval_voice`) | Randy Eval, RandyEvalOutput |
| Cross-Stage Consistency Evaluator (`eval_cross_stage`) | CrossGEMEval, CrossGEMEvalOutput |

---

## Tier classifications (prescreen score → classification)

| Score Range | Canonical Tier | Retired Name |
|---|---|---|
| 32–40 | `native` | "Native" (unchanged) |
| 20–31 | `high_potential_aspiring` | "High-Potential Aspiring" (unchanged in prose) |
| < 20 | `challenging` | "Tourist" |

---

## Workflow states (in code/database)

| Canonical | Retired |
|---|---|
| `prescreen_complete` | `gatekeeper_complete` |
| `voice_eval_complete` | `randy_eval_complete` |
| `cross_stage_eval_complete` | `cross_gem_eval_complete` |
| `rejected_challenging` | `rejected_tourist` |

---

## Database tables and columns

| Canonical | Retired |
|---|---|
| `pipeline_jobs` | `gem_jobs` |
| `pipeline_artifacts` | `gem_artifacts` |
| `pipeline_status_log` | `gem_status_log` |
| `gp_pipeline.prescreen_score` | `gp_pipeline.gatekeeper_score` |
| `gp_pipeline.prescreen_class` | `gp_pipeline.gatekeeper_class` |

---

## Pydantic class names

| Canonical | Retired |
|---|---|
| `PrescreenReport` | `GatekeeperReport` |
| `PrescreenClassification` | `GatekeeperClassification` |
| `PrescreenContext` | `GatekeeperContext` |
| `LPEmails` | `GEM3Emails` |
| `CrossStageEvalOutput` | `CrossGEMEvalOutput` |
| `CrossStageChecks` | `CrossGEMChecks` |
| `VoiceEvalOutput` | `RandyEvalOutput` |

---

## Schema files

| Canonical | Retired |
|---|---|
| `prescreen_report.json` | `gatekeeper_report.json` |
| `cross_stage_eval.json` | `cross_gem_eval.json` |
| `06_lp_emails.json` | `gem3_emails.json` |
| `voice_eval.json` | `randy_eval.json` |

---

## Pipeline execution path

- **Canonical pipeline executor:** the Python orchestrator at `pcd-gem-engine`. Produces structured JSON artifacts and Supabase persistence. Currently aligned at commit `02193f7` (verified end-to-end against Tamarind Hill Fund III deck on 26 April 2026).

- **Legacy execution path:** the Cowork skill `gp-concierge-pipeline` orchestrating five sub-skills (`gp-concierge-gatekeeper`, `gp-deck-analyst`, `steph-lp-email-specialist`, `gp-taxonomy-ted`, `gp-deal-card-sam`). Still functional, but using retired vocabulary internally. Punchlist item 22 covers eventual retirement.

- **Future Word document renderer:** the Cowork skill `pipeline-report-renderer` (punchlist item 21, not yet built). Will read JSON artifacts from `jobs/<job_id>/artifacts/` and render Word documents matching the 650 Fund II Pipeline Report format. Output will land at `01-Pipeline/<deck-version>/Pipeline_Report.docx` in each GP project folder.

---

## Personal/role names retired from system architecture

The following names remain fine in informal conversation and historical references. They're retired only from system identifiers (class names, stage names, file names, schema field names):

| Name | Replaced by (functional) |
|---|---|
| Steph | LP Emails stage |
| Ted | Preqin Taxonomy stage |
| Sam | Deal Card stage |
| Randy (in eval class names) | Voice Evaluator |
| Gatekeeper (as stage name) | Prescreen |

---

## Common retired phrases to flag

When auditing documents, look for these specific phrases — they indicate pre-rename text:

- "GEM 1," "GEM 2," "GEM 3," "GEM 4," "GEM 5"
- "Gatekeeper Intake Report"
- "Tourist tier" or "Tourist classification"
- "Step 1 — Gatekeeper," "Step 2 — Extractor," "Step 3 — Steph," "Step 4 — Ted," "Step 5 — Sam"
- "GEM Engine" or "gem-engine"
- "Randy Eval"
- "Cross-GEM evaluator"

---

## What this lookup does not cover

- **Project name `pcd-gem-engine`** — the Python project itself still carries the "gem-engine" name. Punchlist item 8 covers eventual project rename.
- **Cowork skill names like `gp-concierge-gatekeeper`** — the legacy skill names retain "gatekeeper" until punchlist item 22 retires or modernizes them.
- **External documents (e.g., past memos, customer-facing reports already shipped)** — historical documents are not retroactively updated. Only forward-going content uses canonical vocabulary.

---

*This document is a working reference. When the next round of changes happens (item 21 renderer skill, item 8 project rename, etc. — item 6 JSON John was completed 24 July 2026), update this lookup in the same session as the change. Drift starts the moment two sources of truth disagree about the canonical name.*

## Related Context

- [[pcd-gem-engine-runtime]]
- [[gp-concierge-pipeline]]
