"""Targeted downstream artifact repair.

Regeneration can ONLY modify downstream artifacts (GEM 3 emails, GEM 5 deal card).
Upstream truth layers (GEM 1, 2, 2.5) are immutable.
"""

from __future__ import annotations

from config.settings import DOWNSTREAM_REPAIRABLE_STAGES, UPSTREAM_TRUTH_STAGES
from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossGEMEvalOutput,
    EvalDecision,
    GatekeeperReport,
    RandyEvalOutput,
    StageResult,
    TaxonomyOutput,
)
from src.persistence import load_artifact, load_parsed_text
from src.stage_runner import run_stage


def identify_repair_targets(
    randy_eval: RandyEvalOutput,
    cross_eval: CrossGEMEvalOutput,
) -> set[str]:
    """Determine which downstream artifacts need repair based on evaluator outputs."""
    targets = set()

    if randy_eval.decision == EvalDecision.REVISE:
        targets.add("gem3_randy_emails")

    if cross_eval.decision == EvalDecision.REVISE:
        for artifact in cross_eval.artifacts_requiring_repair:
            if artifact in DOWNSTREAM_REPAIRABLE_STAGES:
                targets.add(artifact)

    # Safety: never allow upstream stages to be targeted
    targets -= UPSTREAM_TRUTH_STAGES
    return targets


def build_revision_instructions(
    artifact_name: str,
    randy_eval: RandyEvalOutput,
    cross_eval: CrossGEMEvalOutput,
) -> str:
    """Compile revision instructions from both evaluators for a specific artifact."""
    parts = []

    if artifact_name == "gem3_randy_emails" and randy_eval.revision_summary:
        parts.append(f"RANDY VOICE EVALUATOR FEEDBACK:\n{randy_eval.revision_summary}")

        # Include per-email instructions
        for email_eval in randy_eval.emails_evaluated:
            if email_eval.revision_instructions:
                parts.append(f"  [{email_eval.label}]: {email_eval.revision_instructions}")

    if cross_eval.revision_instructions:
        parts.append(f"CROSS-GEM CONSISTENCY FEEDBACK:\n{cross_eval.revision_instructions}")

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
    analyst = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    angle = load_artifact(job_id, "gem2_5_angle_brief", AngleBrief)
    gk = load_artifact(job_id, "gem1_gatekeeper", GatekeeperReport)

    context = {
        "analyst_extraction_report": analyst.model_dump_json(indent=2),
        "angle_brief": angle.model_dump_json(indent=2),
        "gatekeeper_report": gk.model_dump_json(indent=2),
    }

    # Deal Card also needs taxonomy + deck text
    if artifact_name == "gem5_deal_card":
        taxonomy = load_artifact(job_id, "gem4_taxonomy_ted", TaxonomyOutput)
        parsed = load_parsed_text(job_id)
        context["taxonomy_output"] = taxonomy.model_dump_json(indent=2)
        context["deck_text"] = parsed["full_text"]

    return run_stage(
        stage_name=artifact_name,
        job_id=job_id,
        context=context,
        system_suffix=f"--- REVISION INSTRUCTIONS ---\n{revision_instructions}",
    )
