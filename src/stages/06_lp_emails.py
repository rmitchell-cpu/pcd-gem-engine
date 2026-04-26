"""Stage 06: LP Email Drafts."""

from src.models import AnalystExtraction, AngleBrief, PrescreenReport, StageResult
from src.persistence import load_artifact
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run LP email drafting using Analyst Report + Angle Brief."""
    # TODO: load 01_fund_extract artifact for verified facts ground truth
    an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
    ab = load_artifact(job_id, "03_angle_brief", AngleBrief)
    gk = load_artifact(job_id, "prescreen", PrescreenReport)
    return run_stage(
        stage_name="06_lp_emails",
        job_id=job_id,
        context={
            "analyst_extraction_report": an.model_dump_json(indent=2),
            "angle_brief": ab.model_dump_json(indent=2),
            "prescreen_report": gk.model_dump_json(indent=2),
        },
    )
