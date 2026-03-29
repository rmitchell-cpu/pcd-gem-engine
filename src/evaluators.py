"""Evaluator execution: Randy Voice QA and Cross-GEM Consistency."""

from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossGEMEvalOutput,
    DealCard,
    GatekeeperReport,
    GEM3Emails,
    RandyEvalOutput,
    StageResult,
)
from src.persistence import load_artifact
from src.stage_runner import run_stage


def run_randy_evaluator(job_id: str) -> StageResult:
    """Evaluate LP email drafts against Randy voice standards."""
    emails = load_artifact(job_id, "gem3_randy_emails", GEM3Emails)
    analyst = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    angle = load_artifact(job_id, "gem2_5_angle_brief", AngleBrief)

    return run_stage(
        stage_name="eval_randy_voice",
        job_id=job_id,
        context={
            "gem3_emails": emails.model_dump_json(indent=2),
            "analyst_extraction_report": analyst.model_dump_json(indent=2),
            "angle_brief": angle.model_dump_json(indent=2),
        },
    )


def run_cross_gem_evaluator(job_id: str) -> StageResult:
    """Check cross-GEM consistency between upstream truth and downstream artifacts."""
    gk = load_artifact(job_id, "gem1_gatekeeper", GatekeeperReport)
    analyst = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    angle = load_artifact(job_id, "gem2_5_angle_brief", AngleBrief)
    emails = load_artifact(job_id, "gem3_randy_emails", GEM3Emails)
    deal_card = load_artifact(job_id, "gem5_deal_card", DealCard)

    return run_stage(
        stage_name="eval_cross_gem",
        job_id=job_id,
        context={
            "gatekeeper_report": gk.model_dump_json(indent=2),
            "analyst_extraction_report": analyst.model_dump_json(indent=2),
            "angle_brief": angle.model_dump_json(indent=2),
            "gem3_emails": emails.model_dump_json(indent=2),
            "deal_card": deal_card.model_dump_json(indent=2),
        },
    )
