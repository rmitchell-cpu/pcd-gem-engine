"""Schema validation for stage outputs using Pydantic models."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, ValidationError

from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossGEMEvalOutput,
    DealCard,
    GatekeeperReport,
    GEM3Emails,
    RandyEvalOutput,
    TaxonomyOutput,
)

# Maps stage name → Pydantic model class
STAGE_SCHEMA_MAP: dict[str, Type[BaseModel]] = {
    "gem1_gatekeeper": GatekeeperReport,
    "gem2_extractor": AnalystExtraction,
    "gem2_5_angle_brief": AngleBrief,
    "gem3_randy_emails": GEM3Emails,
    "gem4_taxonomy_ted": TaxonomyOutput,
    "gem5_deal_card": DealCard,
    "eval_randy_voice": RandyEvalOutput,
    "eval_cross_gem": CrossGEMEvalOutput,
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
