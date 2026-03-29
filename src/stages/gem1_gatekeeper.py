"""GEM 1: Gatekeeper — intake screening stage."""

from src.models import GatekeeperReport, StageResult, WorkflowState
from src.persistence import load_artifact, load_parsed_text
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run the Gatekeeper stage using the parsed deck text."""
    parsed = load_parsed_text(job_id)
    return run_stage(
        stage_name="gem1_gatekeeper",
        job_id=job_id,
        context={"deck_text": parsed["full_text"]},
    )
