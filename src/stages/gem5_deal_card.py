"""GEM 5: Summary Sam — Deal Card / Tear Sheet generation."""

from src.models import AnalystExtraction, StageResult, TaxonomyOutput
from src.persistence import load_artifact, load_parsed_text
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run Deal Card generation using three sources."""
    an = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    tx = load_artifact(job_id, "gem4_taxonomy_ted", TaxonomyOutput)
    parsed = load_parsed_text(job_id)
    return run_stage(
        stage_name="gem5_deal_card",
        job_id=job_id,
        context={
            "analyst_extraction_report": an.model_dump_json(indent=2),
            "taxonomy_output": tx.model_dump_json(indent=2),
            "deck_text": parsed["full_text"],
        },
    )
