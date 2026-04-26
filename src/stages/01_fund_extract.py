"""
Stage 01: Fund Extract (JSON John)

Structured JSON extraction of fund mechanics, terms, strategy, and historical
track record from the GP deck. Output is the verified-facts ground truth used
by all downstream stages.

This stage is currently a stub. Full implementation is pending the prompt
file at prompts/01_fund_extract.md being completed.
"""

stage_name = "01_fund_extract"


def run(deck_text: str, deck_path: str = None) -> dict:
    """
    Run the fund extraction stage.

    Returns a dict matching the JSON John schema.
    """
    raise NotImplementedError(
        "01_fund_extract stage is a placeholder. "
        "Implement after orchestrator rename pass is verified."
    )
