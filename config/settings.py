"""Global configuration for the PCD GEM Engine."""

from pathlib import Path

# Paths
ENGINE_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ENGINE_ROOT / "prompts"
SCHEMAS_DIR = ENGINE_ROOT / "schemas"
JOBS_DIR = ENGINE_ROOT / "jobs"
REFERENCES_DIR = PROMPTS_DIR / "references"

# LLM
MODEL = "claude-opus-4-6"
MAX_TOKENS = 16384
TEMPERATURE = 0.2  # Low temperature for consistency and factual precision

# Retry
MAX_STAGE_RETRIES = 2

# Stage execution order (canonical pipeline sequence)
PIPELINE_STAGES = [
    "gem1_gatekeeper",
    "gem2_extractor",
    "gem2_5_angle_brief",
    "gem4_taxonomy_ted",
    "gem5_deal_card",
    "gem3_randy_emails",
]

# Evaluator names
EVALUATORS = [
    "eval_randy_voice",
    "eval_cross_gem",
]

# Truth hierarchy: these stages are upstream sources of truth and cannot be
# modified by the regeneration module.
UPSTREAM_TRUTH_STAGES = frozenset({
    "gem1_gatekeeper",
    "gem2_extractor",
    "gem2_5_angle_brief",
})

# Downstream artifacts that may be repaired by regeneration.
DOWNSTREAM_REPAIRABLE_STAGES = frozenset({
    "gem3_randy_emails",
    "gem5_deal_card",
})

# Maximum regeneration attempts before declaring failure.
MAX_REGENERATION_ATTEMPTS = 2

# Formatting rules (PCD Global Operating System)
CURRENCY_FORMAT = "US$"  # e.g. US$150M
DATE_FORMAT = "DD MM YYYY"  # e.g. 21 02 2026
