"""Prescreen — intake screening stage."""

from src.models import PrescreenReport, StageResult, WorkflowState
from src.persistence import load_artifact, load_parsed_text
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run the prescreen stage using the parsed deck text."""
    parsed = load_parsed_text(job_id)
    return run_stage(
        stage_name="prescreen",
        job_id=job_id,
        context={"deck_text": parsed["full_text"]},
    )
