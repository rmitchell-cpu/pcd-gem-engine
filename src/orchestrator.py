"""Pipeline orchestrator: stage sequencing, routing, state management."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from config.settings import (
    DOWNSTREAM_REPAIRABLE_STAGES,
    JOBS_DIR,
    MAX_REGENERATION_ATTEMPTS,
    UPSTREAM_TRUTH_STAGES,
)
from src.ingestion import extract_metadata, extract_text_from_pdf
from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossStageEvalOutput,
    DealCard,
    EvalDecision,
    PrescreenClassification,
    PrescreenReport,
    LPEmails,
    VoiceEvalOutput,
    ReviewBundleManifest,
    StageResult,
    TaxonomyOutput,
    WorkflowState,
)
from src.persistence import (
    _sb_update_gp_pipeline,
    _sb_upsert_job,
    artifact_exists,
    create_job,
    load_artifact,
    load_manifest,
    load_parsed_text,
    log_transition,
    save_bundle,
    save_parsed_text,
    update_state,
)
from src.stage_runner import run_stage


def _log_and_update(job_id: str, stage: str, from_state: WorkflowState, to_state: WorkflowState, result: StageResult):
    """Helper to log a transition and update manifest state."""
    log_transition(
        job_id=job_id,
        stage_name=stage,
        from_state=from_state,
        to_state=to_state,
        result="success" if result.success else "failed",
        notes=result.error,
        model_version=result.model_version,
        prompt_version=result.prompt_hash,
        token_usage={"input": result.input_tokens, "output": result.output_tokens},
    )
    update_state(job_id, to_state)


def _fail(job_id: str, stage: str, result: StageResult, from_state: WorkflowState) -> str:
    """Mark job as failed and return error message."""
    _log_and_update(job_id, stage, from_state, WorkflowState.FAILED, result)
    return f"PIPELINE FAILED at {stage}: {result.error}"


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(deck_path: str, verbose: bool = True) -> str:
    """Execute the full Concierge pipeline on a single deck.

    Returns the path to the review bundle JSON.
    """
    def _print(msg: str):
        if verbose:
            print(msg, flush=True)

    # ------------------------------------------------------------------
    # Step 0: Intake
    # ------------------------------------------------------------------
    _print("[INTAKE] Creating job...")
    manifest = create_job(deck_path)
    job_id = manifest.job_id
    _print(f"  Job ID: {job_id}")

    # ------------------------------------------------------------------
    # Step 1: Parse deck
    # ------------------------------------------------------------------
    _print("[PARSE] Extracting text from deck...")
    try:
        full_text, page_texts = extract_text_from_pdf(manifest.deck_path)
        meta = extract_metadata(manifest.deck_path)
        save_parsed_text(job_id, full_text, page_texts)
        update_state(job_id, WorkflowState.PARSED)
        log_transition(job_id, "parse", WorkflowState.UPLOADED, WorkflowState.PARSED, "success",
                       notes=f"Pages: {meta.get('page_count', '?')}")
        _print(f"  Parsed {meta.get('page_count', '?')} pages")
    except Exception as e:
        update_state(job_id, WorkflowState.FAILED)
        log_transition(job_id, "parse", WorkflowState.UPLOADED, WorkflowState.FAILED, "failed", notes=str(e))
        return f"PIPELINE FAILED at parse: {e}"

    deck_text = full_text

    # ------------------------------------------------------------------
    # Step 2: prescreen — Intake gating
    # ------------------------------------------------------------------
    _print("[PRESCREEN] Running prescreen...")
    gk_result = run_stage("prescreen", job_id, {"deck_text": deck_text})
    if not gk_result.success:
        return _fail(job_id, "prescreen", gk_result, WorkflowState.PARSED)

    _log_and_update(job_id, "prescreen", WorkflowState.PARSED, WorkflowState.PRESCREEN_COMPLETE, gk_result)
    prescreen_report: PrescreenReport = load_artifact(job_id, "prescreen", PrescreenReport)
    fund_name = prescreen_report.fund_name
    update_state(job_id, WorkflowState.PRESCREEN_COMPLETE, fund_name=fund_name)
    _print(f"  Score: {prescreen_report.total_score}/40 — {prescreen_report.classification.value}")

    # Supabase: update pipeline_jobs with score + update/create gp_pipeline central record
    _sb_upsert_job(job_id, {
        "fund_name": fund_name,
        "prescreen_score": prescreen_report.total_score,
        "prescreen_class": prescreen_report.classification.value,
    })
    _sb_update_gp_pipeline(
        job_id, fund_name,
        score=prescreen_report.total_score,
        classification=prescreen_report.classification.value,
        state=WorkflowState.PRESCREEN_COMPLETE.value,
    )

    # Challenging routing: hard stop for LP-facing artifacts
    if prescreen_report.classification == PrescreenClassification.CHALLENGING:
        _print("[ROUTING] Challenging classification — stopping LP outreach pipeline.")
        update_state(job_id, WorkflowState.REJECTED_CHALLENGING)
        log_transition(job_id, "routing", WorkflowState.PRESCREEN_COMPLETE,
                       WorkflowState.REJECTED_CHALLENGING, "success",
                       notes="Challenging classification — LP artifacts suppressed")
        # Supabase: mark gp_pipeline as rejected (Challenging tier)
        _sb_update_gp_pipeline(
            job_id, fund_name,
            score=prescreen_report.total_score,
            classification=prescreen_report.classification.value,
            state=WorkflowState.REJECTED_CHALLENGING.value,
        )
        # Still produce a minimal review bundle with just the prescreen result
        bundle = _assemble_bundle(job_id, fund_name, prescreen_report, evaluator_passed=False, regen_count=0)
        bundle_path = save_bundle(job_id, bundle)
        _print(f"  Internal-only bundle saved: {bundle_path}")
        return bundle_path

    # ------------------------------------------------------------------
    # TODO: Insert 01_fund_extract (JSON John) stage here when JSON John
    # is fully implemented. This stage produces the verified-facts ground
    # truth (Fund_Mechanics_and_Terms, etc.) consumed by 02_deck_analysis
    # and downstream stages. See src/stages/01_fund_extract.py and
    # prompts/01_fund_extract.md for current placeholder.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Step 3: 02_deck_analysis — Analyst Extractor
    # ------------------------------------------------------------------
    _print("[02_deck_analysis] Running Analyst Extractor...")
    analyst_result = run_stage("02_deck_analysis", job_id, {"deck_text": deck_text})
    if not analyst_result.success:
        return _fail(job_id, "02_deck_analysis", analyst_result, WorkflowState.PRESCREEN_COMPLETE)

    _log_and_update(job_id, "02_deck_analysis", WorkflowState.PRESCREEN_COMPLETE, WorkflowState.ANALYST_COMPLETE, analyst_result)
    analyst: AnalystExtraction = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
    _print(f"  Gaps found: {len(analyst.information_gaps)}, Interview Qs: {len(analyst.required_interview_questions)}")

    # ------------------------------------------------------------------
    # Step 4: 03_angle_brief — Angle Brief
    # ------------------------------------------------------------------
    _print("[03_angle_brief] Running Angle Brief...")
    gk_json = prescreen_report.model_dump_json(indent=2)
    analyst_json = analyst.model_dump_json(indent=2)

    angle_result = run_stage("03_angle_brief", job_id, {
        "prescreen_report": gk_json,
        "analyst_extraction_report": analyst_json,
    })
    if not angle_result.success:
        return _fail(job_id, "03_angle_brief", angle_result, WorkflowState.ANALYST_COMPLETE)

    _log_and_update(job_id, "03_angle_brief", WorkflowState.ANALYST_COMPLETE, WorkflowState.ANGLE_BRIEF_COMPLETE, angle_result)
    angle: AngleBrief = load_artifact(job_id, "03_angle_brief", AngleBrief)
    _print(f"  Primary angle: {angle.primary_angle.value}, CTA: {angle.recommended_cta_type.value}")

    # ------------------------------------------------------------------
    # Step 5: 04_preqin_taxonomy — Taxonomy Ted
    # ------------------------------------------------------------------
    _print("[04_preqin_taxonomy] Running Taxonomy Ted...")
    taxonomy_result = run_stage("04_preqin_taxonomy", job_id, {
        "analyst_extraction_report": analyst_json,
        "deck_text": deck_text,
    })
    if not taxonomy_result.success:
        return _fail(job_id, "04_preqin_taxonomy", taxonomy_result, WorkflowState.ANGLE_BRIEF_COMPLETE)

    _log_and_update(job_id, "04_preqin_taxonomy", WorkflowState.ANGLE_BRIEF_COMPLETE, WorkflowState.TAXONOMY_COMPLETE, taxonomy_result)
    taxonomy: TaxonomyOutput = load_artifact(job_id, "04_preqin_taxonomy", TaxonomyOutput)
    _print(f"  Tags: {len(taxonomy.canonical_strategy_tags)}, Matrix entries: {len(taxonomy.translation_matrix)}")

    # ------------------------------------------------------------------
    # Step 6: 05_deal_card — Deal Card (Summary Sam)
    # ------------------------------------------------------------------
    _print("[05_deal_card] Running Deal Card (Summary Sam)...")
    taxonomy_json = taxonomy.model_dump_json(indent=2)
    deal_card_result = run_stage("05_deal_card", job_id, {
        "analyst_extraction_report": analyst_json,
        "taxonomy_output": taxonomy_json,
        "deck_text": deck_text,
    })
    if not deal_card_result.success:
        return _fail(job_id, "05_deal_card", deal_card_result, WorkflowState.TAXONOMY_COMPLETE)

    _log_and_update(job_id, "05_deal_card", WorkflowState.TAXONOMY_COMPLETE, WorkflowState.DEAL_CARD_COMPLETE, deal_card_result)
    _print("  Deal Card generated.")

    # ------------------------------------------------------------------
    # Step 7: 06_lp_emails — LP Email Drafts
    # ------------------------------------------------------------------
    _print("[06_lp_emails] Running LP Email Drafts...")
    angle_json = angle.model_dump_json(indent=2)
    email_result = run_stage("06_lp_emails", job_id, {
        "analyst_extraction_report": analyst_json,
        "angle_brief": angle_json,
        "prescreen_report": gk_json,
    })
    if not email_result.success:
        return _fail(job_id, "06_lp_emails", email_result, WorkflowState.DEAL_CARD_COMPLETE)

    _log_and_update(job_id, "06_lp_emails", WorkflowState.DEAL_CARD_COMPLETE, WorkflowState.EMAIL_DRAFTS_COMPLETE, email_result)
    _print("  4 email variants generated.")

    # ------------------------------------------------------------------
    # Step 8: Evaluators
    # ------------------------------------------------------------------
    _print("[EVAL] Running Voice Evaluator...")
    emails: LPEmails = load_artifact(job_id, "06_lp_emails", LPEmails)
    emails_json = emails.model_dump_json(indent=2)

    voice_eval_result = run_stage("eval_voice", job_id, {
        "lp_emails": emails_json,
        "analyst_extraction_report": analyst_json,
        "angle_brief": angle_json,
    })
    if not voice_eval_result.success:
        return _fail(job_id, "eval_voice", voice_eval_result, WorkflowState.EMAIL_DRAFTS_COMPLETE)

    _log_and_update(job_id, "eval_voice", WorkflowState.EMAIL_DRAFTS_COMPLETE, WorkflowState.VOICE_EVAL_COMPLETE, voice_eval_result)
    voice_eval: VoiceEvalOutput = load_artifact(job_id, "eval_voice", VoiceEvalOutput)
    _print(f"  Voice eval: {'PASS' if voice_eval.overall_pass else 'REVISE'}")

    _print("[EVAL] Running Cross-Stage Consistency Evaluator...")
    deal_card: DealCard = load_artifact(job_id, "05_deal_card", DealCard)
    deal_card_json = deal_card.model_dump_json(indent=2)

    cross_eval_result = run_stage("eval_cross_stage", job_id, {
        "prescreen_report": gk_json,
        "analyst_extraction_report": analyst_json,
        "angle_brief": angle_json,
        "lp_emails": emails_json,
        "deal_card": deal_card_json,
    })
    if not cross_eval_result.success:
        return _fail(job_id, "eval_cross_stage", cross_eval_result, WorkflowState.VOICE_EVAL_COMPLETE)

    _log_and_update(job_id, "eval_cross_stage", WorkflowState.VOICE_EVAL_COMPLETE, WorkflowState.CROSS_STAGE_EVAL_COMPLETE, cross_eval_result)
    cross_eval: CrossStageEvalOutput = load_artifact(job_id, "eval_cross_stage", CrossStageEvalOutput)
    _print(f"  Cross-stage eval: {'PASS' if cross_eval.overall_pass else 'REVISE'}")

    # ------------------------------------------------------------------
    # Step 9: Regeneration (if needed)
    # ------------------------------------------------------------------
    regen_count = 0
    if voice_eval.decision == EvalDecision.REVISE or cross_eval.decision == EvalDecision.REVISE:
        _print("[REGEN] Evaluators flagged issues — running regeneration...")
        update_state(job_id, WorkflowState.REGENERATION_REQUIRED)

        for regen_attempt in range(MAX_REGENERATION_ATTEMPTS):
            regen_count += 1
            _print(f"  Regeneration attempt {regen_count}...")

            # Determine which downstream artifacts need repair
            artifacts_to_repair = set()
            if voice_eval.decision == EvalDecision.REVISE:
                artifacts_to_repair.add("06_lp_emails")
            if cross_eval.decision == EvalDecision.REVISE:
                for art in cross_eval.artifacts_requiring_repair:
                    if art in DOWNSTREAM_REPAIRABLE_STAGES:
                        artifacts_to_repair.add(art)

            # Regenerate each flagged downstream artifact
            for artifact_name in artifacts_to_repair:
                _print(f"    Repairing {artifact_name}...")
                revision_instructions = ""
                if artifact_name == "06_lp_emails" and voice_eval.revision_summary:
                    revision_instructions = voice_eval.revision_summary
                if cross_eval.revision_instructions:
                    revision_instructions += "\n" + cross_eval.revision_instructions

                # Build context with revision instructions appended
                regen_context = {
                    "analyst_extraction_report": analyst_json,
                    "angle_brief": angle_json,
                    "prescreen_report": gk_json,
                }
                if artifact_name == "05_deal_card":
                    regen_context["taxonomy_output"] = taxonomy_json
                    regen_context["deck_text"] = deck_text

                regen_result = run_stage(
                    artifact_name, job_id, regen_context,
                    system_suffix=f"REVISION INSTRUCTIONS:\n{revision_instructions}",
                )
                if not regen_result.success:
                    _print(f"    Repair of {artifact_name} failed: {regen_result.error}")

            # Re-run evaluators to check the repair
            emails = load_artifact(job_id, "06_lp_emails", LPEmails)
            emails_json = emails.model_dump_json(indent=2)
            deal_card = load_artifact(job_id, "05_deal_card", DealCard)
            deal_card_json = deal_card.model_dump_json(indent=2)

            voice_eval_result = run_stage("eval_voice", job_id, {
                "lp_emails": emails_json,
                "analyst_extraction_report": analyst_json,
                "angle_brief": angle_json,
            })
            if voice_eval_result.success:
                voice_eval = load_artifact(job_id, "eval_voice", VoiceEvalOutput)

            cross_eval_result = run_stage("eval_cross_stage", job_id, {
                "prescreen_report": gk_json,
                "analyst_extraction_report": analyst_json,
                "angle_brief": angle_json,
                "lp_emails": emails_json,
                "deal_card": deal_card_json,
            })
            if cross_eval_result.success:
                cross_eval = load_artifact(job_id, "eval_cross_stage", CrossStageEvalOutput)

            if voice_eval.overall_pass and cross_eval.overall_pass:
                _print("  Regeneration succeeded — evaluators now pass.")
                break
        else:
            _print(f"  WARNING: Evaluators still failing after {MAX_REGENERATION_ATTEMPTS} regeneration attempts.")

        update_state(job_id, WorkflowState.REGENERATED)
        log_transition(job_id, "regeneration", WorkflowState.REGENERATION_REQUIRED,
                       WorkflowState.REGENERATED, "success",
                       notes=f"Regen attempts: {regen_count}")

    # ------------------------------------------------------------------
    # Step 10: Assemble review bundle
    # ------------------------------------------------------------------
    _print("[BUNDLE] Assembling review bundle...")
    evaluator_passed = voice_eval.overall_pass and cross_eval.overall_pass
    bundle = _assemble_bundle(job_id, fund_name, prescreen_report, evaluator_passed, regen_count)
    bundle_path = save_bundle(job_id, bundle)
    update_state(job_id, WorkflowState.HUMAN_REVIEW_PENDING)
    log_transition(job_id, "bundle", WorkflowState.CROSS_STAGE_EVAL_COMPLETE,
                   WorkflowState.HUMAN_REVIEW_PENDING, "success")

    # Supabase: update gp_pipeline with final state
    _sb_update_gp_pipeline(
        job_id, fund_name,
        score=prescreen_report.total_score,
        classification=prescreen_report.classification.value,
        state=WorkflowState.HUMAN_REVIEW_PENDING.value,
    )

    _print(f"\n{'='*60}")
    _print(f"PIPELINE COMPLETE — {fund_name}")
    _print(f"  Job: {job_id}")
    _print(f"  Score: {prescreen_report.total_score}/40 ({prescreen_report.classification.value})")
    _print(f"  Evaluators: {'PASS' if evaluator_passed else 'ISSUES REMAIN'}")
    _print(f"  Regeneration rounds: {regen_count}")
    _print(f"  Bundle: {bundle_path}")
    _print(f"  Status: HUMAN REVIEW PENDING")
    _print(f"{'='*60}")

    return bundle_path


# ---------------------------------------------------------------------------
# Single-stage rerun
# ---------------------------------------------------------------------------

def rerun_stage(job_id: str, stage_name: str) -> StageResult:
    """Rerun a single stage using persisted upstream artifacts."""
    manifest = load_manifest(job_id)
    parsed = load_parsed_text(job_id)
    deck_text = parsed["full_text"]

    # Build context based on what the stage needs
    context: dict[str, str] = {}

    if stage_name in ("prescreen", "02_deck_analysis"):
        context["deck_text"] = deck_text

    if stage_name == "03_angle_brief":
        gk = load_artifact(job_id, "prescreen", PrescreenReport)
        an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
        context["prescreen_report"] = gk.model_dump_json(indent=2)
        context["analyst_extraction_report"] = an.model_dump_json(indent=2)

    if stage_name == "04_preqin_taxonomy":
        an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
        context["analyst_extraction_report"] = an.model_dump_json(indent=2)
        context["deck_text"] = deck_text

    if stage_name == "05_deal_card":
        an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
        tx = load_artifact(job_id, "04_preqin_taxonomy", TaxonomyOutput)
        context["analyst_extraction_report"] = an.model_dump_json(indent=2)
        context["taxonomy_output"] = tx.model_dump_json(indent=2)
        context["deck_text"] = deck_text

    if stage_name == "06_lp_emails":
        an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
        ab = load_artifact(job_id, "03_angle_brief", AngleBrief)
        gk = load_artifact(job_id, "prescreen", PrescreenReport)
        context["analyst_extraction_report"] = an.model_dump_json(indent=2)
        context["angle_brief"] = ab.model_dump_json(indent=2)
        context["prescreen_report"] = gk.model_dump_json(indent=2)

    if stage_name == "eval_voice":
        an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
        ab = load_artifact(job_id, "03_angle_brief", AngleBrief)
        em = load_artifact(job_id, "06_lp_emails", LPEmails)
        context["lp_emails"] = em.model_dump_json(indent=2)
        context["analyst_extraction_report"] = an.model_dump_json(indent=2)
        context["angle_brief"] = ab.model_dump_json(indent=2)

    if stage_name == "eval_cross_stage":
        gk = load_artifact(job_id, "prescreen", PrescreenReport)
        an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
        ab = load_artifact(job_id, "03_angle_brief", AngleBrief)
        em = load_artifact(job_id, "06_lp_emails", LPEmails)
        dc = load_artifact(job_id, "05_deal_card", DealCard)
        context["prescreen_report"] = gk.model_dump_json(indent=2)
        context["analyst_extraction_report"] = an.model_dump_json(indent=2)
        context["angle_brief"] = ab.model_dump_json(indent=2)
        context["lp_emails"] = em.model_dump_json(indent=2)
        context["deal_card"] = dc.model_dump_json(indent=2)

    if not context:
        raise ValueError(
            f"rerun_stage: unknown or unsupported stage_name {stage_name!r}. "
            "Supported: prescreen, 02_deck_analysis, 03_angle_brief, "
            "04_preqin_taxonomy, 05_deal_card, 06_lp_emails, eval_voice, eval_cross_stage."
        )

    result = run_stage(stage_name, job_id, context)
    return result


# ---------------------------------------------------------------------------
# Bundle assembly
# ---------------------------------------------------------------------------

def _assemble_bundle(
    job_id: str,
    fund_name: str,
    prescreen_report: PrescreenReport,
    evaluator_passed: bool,
    regen_count: int,
) -> ReviewBundleManifest:
    """Assemble the review bundle manifest from persisted artifacts."""
    manifest = load_manifest(job_id)
    artifacts = {}
    flagged = []
    manual_attention = []

    # Collect all existing artifacts
    artifact_dir = JOBS_DIR / job_id / "artifacts"
    if artifact_dir.exists():
        for f in artifact_dir.iterdir():
            if f.suffix == ".json" and f.name != "parsed_deck.json":
                stage = f.stem
                artifacts[stage] = f"artifacts/{f.name}"

    if not evaluator_passed:
        flagged.append("Evaluators did not fully pass — review downstream artifacts carefully")
    if regen_count > 0:
        flagged.append(f"Regeneration was triggered {regen_count} time(s)")
    if prescreen_report.classification == PrescreenClassification.CHALLENGING:
        manual_attention.append("Challenging classification — no LP outreach generated")

    return ReviewBundleManifest(
        job_id=job_id,
        fund_name=fund_name,
        created_at=datetime.utcnow(),
        pipeline_status=manifest.current_state,
        prescreen_class=prescreen_report.classification,
        prescreen_score=prescreen_report.total_score,
        evaluator_passed=evaluator_passed,
        regeneration_count=regen_count,
        artifacts=artifacts,
        flagged_items=flagged,
        requires_manual_attention=manual_attention,
    )
