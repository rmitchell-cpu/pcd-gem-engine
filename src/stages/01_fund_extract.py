"""Stage 01: Fund Extract (JSON John) — structured fund-terms extraction.

Produces the verified-facts ground truth (fund mechanics, mandate, target
returns, strategy-specific metrics, track record, qualitative drivers)
consumed by downstream stages.
"""

from src.models import StageResult
from src.persistence import load_parsed_text
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run the Fund Extract using the parsed deck text."""
    parsed = load_parsed_text(job_id)
    return run_stage(
        stage_name="01_fund_extract",
        job_id=job_id,
        context={"deck_text": parsed["full_text"]},
    )
