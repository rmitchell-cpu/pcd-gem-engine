"""Evaluator execution: Voice QA and Cross-Stage Consistency."""

from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossStageEvalOutput,
    DealCard,
    LPEmails,
    PrescreenReport,
    StageResult,
    VoiceEvalOutput,
)
from src.persistence import load_artifact
from src.stage_runner import run_stage


def run_voice_evaluator(job_id: str) -> StageResult:
    """Evaluate LP email drafts against the voice profile standards."""
    emails = load_artifact(job_id, "06_lp_emails", LPEmails)
    analyst = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
    angle = load_artifact(job_id, "03_angle_brief", AngleBrief)

    return run_stage(
        stage_name="eval_voice",
        job_id=job_id,
        context={
            "lp_emails": emails.model_dump_json(indent=2),
            "analyst_extraction_report": analyst.model_dump_json(indent=2),
            "angle_brief": angle.model_dump_json(indent=2),
        },
    )


def run_cross_stage_evaluator(job_id: str) -> StageResult:
    """Check cross-stage consistency between upstream truth and downstream artifacts."""
    gk = load_artifact(job_id, "prescreen", PrescreenReport)
    analyst = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
    angle = load_artifact(job_id, "03_angle_brief", AngleBrief)
    emails = load_artifact(job_id, "06_lp_emails", LPEmails)
    deal_card = load_artifact(job_id, "05_deal_card", DealCard)

    return run_stage(
        stage_name="eval_cross_stage",
        job_id=job_id,
        context={
            "prescreen_report": gk.model_dump_json(indent=2),
            "analyst_extraction_report": analyst.model_dump_json(indent=2),
            "angle_brief": angle.model_dump_json(indent=2),
            "lp_emails": emails.model_dump_json(indent=2),
            "deal_card": deal_card.model_dump_json(indent=2),
        },
    )
