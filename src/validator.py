"""Schema validation for stage outputs using Pydantic models."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, ValidationError

from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossStageEvalOutput,
    DealCard,
    LPEmails,
    PrescreenReport,
    TaxonomyOutput,
    VoiceEvalOutput,
)

# Maps stage name → Pydantic model class
STAGE_SCHEMA_MAP: dict[str, Type[BaseModel]] = {
    "prescreen": PrescreenReport,
    "01_fund_extract": AnalystExtraction,  # placeholder — JSON John schema TBD
    "02_deck_analysis": AnalystExtraction,
    "03_angle_brief": AngleBrief,
    "04_preqin_taxonomy": TaxonomyOutput,
    "05_deal_card": DealCard,
    "06_lp_emails": LPEmails,
    "eval_voice": VoiceEvalOutput,
    "eval_cross_stage": CrossStageEvalOutput,
}


def validate_stage_output(stage_name: str, raw_json: dict) -> BaseModel:
    """Validate raw JSON against the stage's Pydantic schema.

    Returns a validated Pydantic model instance.
    Raises ValidationError if the output does not conform.
    """
    model_class = STAGE_SCHEMA_MAP.get(stage_name)
    if model_class is None:
        raise ValueError(f"No schema registered for stage: {stage_name}")
    return model_class.model_validate(raw_json)


def validation_error_summary(error: ValidationError) -> str:
    """Produce a human-readable summary of validation failures for LLM retry feedback."""
    lines = []
    for err in error.errors():
        loc = " → ".join(str(l) for l in err["loc"])
        lines.append(f"  Field '{loc}': {err['msg']} (type: {err['type']})")
    return "Validation failures:\n" + "\n".join(lines)
