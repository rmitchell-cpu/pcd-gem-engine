"""Stage 02: Analyst Extractor — deep deck analysis stage."""

from src.models import StageResult
from src.persistence import load_parsed_text
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run the Analyst Extractor using the parsed deck text."""
    parsed = load_parsed_text(job_id)
    return run_stage(
        stage_name="02_deck_analysis",
        job_id=job_id,
        context={"deck_text": parsed["full_text"]},
    )
