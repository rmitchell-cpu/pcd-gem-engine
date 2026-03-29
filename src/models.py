"""Pydantic models for all GEM pipeline artifacts and workflow state."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Workflow state machine
# ---------------------------------------------------------------------------

class WorkflowState(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    GATEKEEPER_COMPLETE = "gatekeeper_complete"
    REJECTED_TOURIST = "rejected_tourist"
    ANALYST_COMPLETE = "analyst_complete"
    ANGLE_BRIEF_COMPLETE = "angle_brief_complete"
    TAXONOMY_COMPLETE = "taxonomy_complete"
    DEAL_CARD_COMPLETE = "deal_card_complete"
    EMAIL_DRAFTS_COMPLETE = "email_drafts_complete"
    RANDY_EVAL_COMPLETE = "randy_eval_complete"
    CROSS_GEM_EVAL_COMPLETE = "cross_gem_eval_complete"
    REGENERATION_REQUIRED = "regeneration_required"
    REGENERATED = "regenerated"
    HUMAN_REVIEW_PENDING = "human_review_pending"
    APPROVED = "approved"
    ARCHIVED = "archived"
    FAILED = "failed"


class GatekeeperClassification(str, enum.Enum):
    NATIVE = "native"
    HIGH_POTENTIAL_ASPIRING = "high_potential_aspiring"
    TOURIST = "tourist"


class AnglePrimary(str, enum.Enum):
    FIT_RELEVANCE = "fit_relevance"
    DIFFERENTIATED_EDGE = "differentiated_edge"
    PROOF_REPEATABILITY = "proof_repeatability"
    RIGHT_NOW_TIMING = "right_now_timing"
    SHORT_FORWARDABLE_SUMMARY = "short_forwardable_summary"


class CTAType(str, enum.Enum):
    FIT_CHECK = "fit_check"
    OFFER_SUMMARY = "offer_summary"
    OFFER_DECK = "offer_deck"
    REDIRECT_TO_TEAMMATE = "redirect_to_teammate"
    OFFER_INTRO_IF_USEFUL = "offer_intro_if_useful"


class EmailAngle(str, enum.Enum):
    FIT = "fit"
    EDGE = "edge"
    PROOF = "proof"
    FOLLOWUP = "followup"


class EvalDecision(str, enum.Enum):
    PASS = "pass"
    REVISE = "revise"


# ---------------------------------------------------------------------------
# Job metadata
# ---------------------------------------------------------------------------

class JobManifest(BaseModel):
    job_id: str
    deck_filename: str
    deck_path: str
    fund_name: Optional[str] = None
    created_at: datetime
    current_state: WorkflowState
    last_updated: datetime


class StatusLogEntry(BaseModel):
    timestamp: datetime
    from_state: Optional[WorkflowState] = None
    to_state: WorkflowState
    stage_name: str
    result: str  # "success", "failed", "skipped"
    notes: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None  # content hash
    token_usage: Optional[dict] = None


# ---------------------------------------------------------------------------
# GEM 1: Gatekeeper Report
# ---------------------------------------------------------------------------

class PillarScore(BaseModel):
    score: int = Field(ge=0, le=10)
    diagnostic: str


class GatekeeperReport(BaseModel):
    fund_name: str
    coiled_spring: PillarScore
    inbound_gravity: PillarScore
    outbound_mechanics: PillarScore
    logic_discipline: PillarScore
    total_score: int = Field(ge=0, le=40)
    classification: GatekeeperClassification
    critical_flaw: str
    pcd_intervention_viable: bool
    pcd_intervention_detail: str
    proprietary_penalty_applied: bool = False


# ---------------------------------------------------------------------------
# GEM 2: Analyst Extraction Report
# ---------------------------------------------------------------------------

class InboundGravityDetail(BaseModel):
    claim: Optional[str] = None
    receipts: Optional[str] = None


class OutboundMechanicsDetail(BaseModel):
    chain: Optional[str] = None
    intersection: Optional[str] = None
    why_they_win: Optional[str] = None


class RedFlagDetail(BaseModel):
    key_person_risk: Optional[str] = None
    fee_structure: Optional[str] = None
    track_record_ambiguity: Optional[str] = None


class LogicDisciplineDetail(BaseModel):
    cost_of_capital: Optional[str] = None
    binding_constraints: Optional[str] = None
    hard_no_story: Optional[str] = None


class AnalystExtraction(BaseModel):
    fund_name: str
    executive_summary: Optional[str] = None
    market_definition: Optional[str] = None
    strategic_focus: Optional[str] = None
    context_mastery: Optional[str] = None
    recurring_patterns: Optional[str] = None
    value_creation: Optional[str] = None
    coiled_spring: Optional[str] = None
    cyclical_awareness: Optional[str] = None
    inbound_gravity: InboundGravityDetail = Field(default_factory=InboundGravityDetail)
    outbound_mechanics: OutboundMechanicsDetail = Field(default_factory=OutboundMechanicsDetail)
    red_flags: RedFlagDetail = Field(default_factory=RedFlagDetail)
    logic_discipline: LogicDisciplineDetail = Field(default_factory=LogicDisciplineDetail)
    required_interview_questions: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GEM 2.5: Angle Brief
# ---------------------------------------------------------------------------

class GatekeeperContext(BaseModel):
    classification: str  # "Native", "High-Potential Aspiring", "Tourist", "Not Available"
    assertiveness_guidance: str
    should_generate_outreach: bool


class AngleBrief(BaseModel):
    gatekeeper_context: GatekeeperContext
    primary_angle: AnglePrimary
    angle_rationale: str
    top_points_to_surface: list[str] = Field(min_length=3, max_length=3)
    points_to_avoid_or_deemphasize: list[str] = Field(max_length=2)
    forwardable_sentence_goal: str
    recommended_cta_type: CTAType
    subject_line_direction: str
    tone_guidance_for_gem3: str
    constraints_for_gem3: list[str] = Field(min_length=2, max_length=4)


# ---------------------------------------------------------------------------
# GEM 4: Taxonomy Output
# ---------------------------------------------------------------------------

class TranslationMatrixEntry(BaseModel):
    fund_theme: str
    context_evidence: str
    primary_match: str
    secondary_matches: list[str] = Field(default_factory=list)
    type: str  # "industry" or "vertical"


class SearchStrategy(BaseModel):
    verticals: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class BooleanStrings(BaseModel):
    broad_thesis: str
    niche_deep_tech: str
    geo_specific: str


class TaxonomyOutput(BaseModel):
    fund_name: str
    strategy_summary: Optional[str] = None
    translation_matrix: list[TranslationMatrixEntry] = Field(default_factory=list)
    search_strategy: SearchStrategy = Field(default_factory=SearchStrategy)
    boolean_strings: BooleanStrings
    canonical_strategy_tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# GEM 5: Deal Card
# ---------------------------------------------------------------------------

class RightNowWindow(BaseModel):
    dislocation: str
    catalyst: str


class SourcingForensics(BaseModel):
    receipts: str
    mechanism: str


class DealCardLogicDiscipline(BaseModel):
    cost_of_capital: str
    binding_constraints: str
    discipline_evidence: str


class TrackRecord(BaseModel):
    performance: str
    fund_terms: str


class DealCard(BaseModel):
    fund_name: str
    strategy_tag: str
    target_fund_size: str
    geography: str
    as_of_date: str
    right_now_window: RightNowWindow
    sourcing_forensics: SourcingForensics
    logic_discipline: DealCardLogicDiscipline
    track_record: TrackRecord
    action_cta: str


# ---------------------------------------------------------------------------
# GEM 3: LP Email Drafts
# ---------------------------------------------------------------------------

class LPEmail(BaseModel):
    label: str
    subject_a: str
    subject_b: str
    body: str
    word_count: int
    angle: EmailAngle


class GEM3Emails(BaseModel):
    fund_name: str
    emails: list[LPEmail] = Field(min_length=4, max_length=4)


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------

class EmailEvaluation(BaseModel):
    label: str
    voice_score: int = Field(ge=1, le=10)
    lp_relevance_score: int = Field(ge=1, le=10)
    cta_quality_score: int = Field(ge=1, le=10)
    forwardability_score: int = Field(ge=1, le=10)
    overall_score: int = Field(ge=1, le=10)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: Optional[str] = None


class RandyEvalOutput(BaseModel):
    overall_pass: bool
    emails_evaluated: list[EmailEvaluation]
    decision: EvalDecision
    revision_summary: Optional[str] = None


class DriftCheck(BaseModel):
    detected: bool = False
    detail: Optional[str] = None


class CrossGEMChecks(BaseModel):
    strategy_drift: DriftCheck = Field(default_factory=DriftCheck)
    urgency_drift: DriftCheck = Field(default_factory=DriftCheck)
    sourcing_edge_drift: DriftCheck = Field(default_factory=DriftCheck)
    unsupported_claims: DriftCheck = Field(default_factory=DriftCheck)
    formatting_violations: DriftCheck = Field(default_factory=DriftCheck)
    classification_misalignment: DriftCheck = Field(default_factory=DriftCheck)


class CrossGEMEvalOutput(BaseModel):
    overall_pass: bool
    checks: CrossGEMChecks
    artifacts_requiring_repair: list[str] = Field(default_factory=list)
    decision: EvalDecision
    revision_instructions: Optional[str] = None


# ---------------------------------------------------------------------------
# Review Bundle Manifest
# ---------------------------------------------------------------------------

class ReviewBundleManifest(BaseModel):
    job_id: str
    fund_name: str
    created_at: datetime
    pipeline_status: WorkflowState
    gatekeeper_classification: GatekeeperClassification
    gatekeeper_score: int
    evaluator_passed: bool
    regeneration_count: int = 0
    artifacts: dict[str, str]  # stage_name -> relative file path
    flagged_items: list[str] = Field(default_factory=list)
    requires_manual_attention: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage execution metadata
# ---------------------------------------------------------------------------

class StageResult(BaseModel):
    stage_name: str
    success: bool
    artifact_path: Optional[str] = None
    error: Optional[str] = None
    model_version: str = ""
    prompt_hash: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = 0
