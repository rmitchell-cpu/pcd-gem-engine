"""GEM 4: Taxonomy Ted — database search translation stage."""

from pathlib import Path

from config.settings import REFERENCES_DIR
from src.models import AnalystExtraction, StageResult
from src.persistence import load_artifact, load_parsed_text
from src.stage_runner import run_stage


def execute(job_id: str) -> StageResult:
    """Run Taxonomy Ted using Analyst Report and deck text."""
    an = load_artifact(job_id, "gem2_extractor", AnalystExtraction)
    parsed = load_parsed_text(job_id)

    context = {
        "analyst_extraction_report": an.model_dump_json(indent=2),
        "deck_text": parsed["full_text"],
    }

    # Inject Preqin taxonomy reference if available
    preqin_path = REFERENCES_DIR / "preqin_taxonomy.md"
    if preqin_path.exists():
        context["preqin_industry_tree"] = preqin_path.read_text()

    return run_stage(
        stage_name="gem4_taxonomy_ted",
        job_id=job_id,
        context=context,
    )
