"""GEM 3: Randy Voice LP Email Drafts."""

from src.models import AnalystExtraction, AngleBrief, GatekeeperReport, StageResult
from src.persistence import load_artifact
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run Randy Voice email drafting using Analyst Report + Angle Brief."""
    an = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    ab = load_artifact(job_id, "gem2_5_angle_brief", AngleBrief)
    gk = load_artifact(job_id, "gem1_gatekeeper", GatekeeperReport)
    return run_stage(
        stage_name="gem3_randy_emails",
        job_id=job_id,
        context={
            "analyst_extraction_report": an.model_dump_json(indent=2),
            "angle_brief": ab.model_dump_json(indent=2),
            "gatekeeper_report": gk.model_dump_json(indent=2),
        },
    )
