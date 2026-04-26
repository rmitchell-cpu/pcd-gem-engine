"""Targeted downstream artifact repair.

Regeneration can ONLY modify downstream artifacts (Stage 06 LP emails, Stage 05 deal card).
Upstream truth layers (prescreen, Stage 02 deck analysis, Stage 03 angle brief) are immutable.
"""

from __future__ import annotations

from config.settings import DOWNSTREAM_REPAIRABLE_STAGES, UPSTREAM_TRUTH_STAGES
from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossStageEvalOutput,
    EvalDecision,
    PrescreenReport,
    StageResult,
    TaxonomyOutput,
    VoiceEvalOutput,
)
from src.persistence import load_artifact, load_parsed_text
from src.stage_runner import run_stage


def identify_repair_targets(
    voice_eval: VoiceEvalOutput,
    cross_eval: CrossStageEvalOutput,
) -> set[str]:
    """Determine which downstream artifacts need repair based on evaluator outputs."""
    targets = set()

    if voice_eval.decision == EvalDecision.REVISE:
        targets.add("06_lp_emails")

    if cross_eval.decision == EvalDecision.REVISE:
        for artifact in cross_eval.artifacts_requiring_repair:
            if artifact in DOWNSTREAM_REPAIRABLE_STAGES:
                targets.add(artifact)

    # Safety: never allow upstream stages to be targeted
    targets -= UPSTREAM_TRUTH_STAGES
    return targets


def build_revision_instructions(
    artifact_name: str,
    voice_eval: VoiceEvalOutput,
    cross_eval: CrossStageEvalOutput,
) -> str:
    """Compile revision instructions from both evaluators for a specific artifact."""
    parts = []

    if artifact_name == "06_lp_emails" and voice_eval.revision_summary:
        parts.append(f"VOICE EVALUATOR FEEDBACK:\n{voice_eval.revision_summary}")

        # Include per-email instructions
        for email_eval in voice_eval.emails_evaluated:
            if email_eval.revision_instructions:
                parts.append(f"  [{email_eval.label}]: {email_eval.revision_instructions}")

    if cross_eval.revision_instructions:
        parts.append(f"CROSS-STAGE CONSISTENCY FEEDBACK:\n{cross_eval.revision_instructions}")

    return "\n\n".join(parts)


def regenerate_artifact(
    job_id: str,
    artifact_name: str,
    revision_instructions: str,
) -> StageResult:
    """Regenerate a single downstream artifact with evaluator feedback.

    The upstream context is loaded from persisted artifacts (immutable).
    The revision instructions are injected as a system suffix.
    """
    # Load upstream context (read-only)
    analyst = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
    angle = load_artifact(job_id, "03_angle_brief", AngleBrief)
    gk = load_artifact(job_id, "prescreen", PrescreenReport)

    context = {
        "analyst_extraction_report": analyst.model_dump_json(indent=2),
        "angle_brief": angle.model_dump_json(indent=2),
        "prescreen_report": gk.model_dump_json(indent=2),
    }

    # Deal Card also needs taxonomy + deck text
    if artifact_name == "05_deal_card":
        taxonomy = load_artifact(job_id, "04_preqin_taxonomy", TaxonomyOutput)
        parsed = load_parsed_text(job_id)
        context["taxonomy_output"] = taxonomy.model_dump_json(indent=2)
        context["deck_text"] = parsed["full_text"]

    return run_stage(
        stage_name=artifact_name,
        job_id=job_id,
        context=context,
        system_suffix=f"--- REVISION INSTRUCTIONS ---\n{revision_instructions}",
    )
