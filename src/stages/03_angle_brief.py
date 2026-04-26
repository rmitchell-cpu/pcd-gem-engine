"""Stage 03: Angle Brief — LP framing strategy stage."""

from src.models import AnalystExtraction, PrescreenReport, StageResult
from src.persistence import load_artifact
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run the Angle Brief using prescreen and analyst outputs."""
    gk = load_artifact(job_id, "prescreen", PrescreenReport)
    an = load_artifact(job_id, "02_deck_analysis", AnalystExtraction)
    return run_stage(
        stage_name="03_angle_brief",
        job_id=job_id,
        context={
            "prescreen_report": gk.model_dump_json(indent=2),
            "analyst_extraction_report": an.model_dump_json(indent=2),
        },
    )
