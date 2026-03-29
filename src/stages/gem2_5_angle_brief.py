"""GEM 2.5: Angle Brief — LP framing strategy stage."""

from src.models import AnalystExtraction, GatekeeperReport, StageResult
from src.persistence import load_artifact
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run the Angle Brief using Gatekeeper and Analyst outputs."""
    gk = load_artifact(job_id, "gem1_gatekeeper", GatekeeperReport)
    an = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    return run_stage(
        stage_name="gem2_5_angle_brief",
        job_id=job_id,
        context={
            "gatekeeper_report": gk.model_dump_json(indent=2),
            "analyst_extraction_report": an.model_dump_json(indent=2),
        },
    )
