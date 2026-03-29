"""Schema validation tests — verify that sample payloads conform to Pydantic models."""

import sys
from pathlib import Path

import pytest

# Ensure engine root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import (
    AnalystExtraction,
    AngleBrief,
    CrossGEMEvalOutput,
    DealCard,
    GatekeeperReport,
    GEM3Emails,
    RandyEvalOutput,
    ReviewBundleManifest,
    TaxonomyOutput,
    WorkflowState,
)


def test_gatekeeper_report_valid():
    data = {
        "fund_name": "Acme Capital Fund III",
        "coiled_spring": {"score": 7, "diagnostic": "Clear regulatory tailwind cited."},
        "inbound_gravity": {"score": 5, "diagnostic": "Claims proprietary flow without mechanism."},
        "outbound_mechanics": {"score": 6, "diagnostic": "Some process language but incomplete chain."},
        "logic_discipline": {"score": 4, "diagnostic": "No cost of capital logic, vague constraints."},
        "total_score": 22,
        "classification": "high_potential_aspiring",
        "critical_flaw": "No differentiated sourcing mechanism documented.",
        "pcd_intervention_viable": True,
        "pcd_intervention_detail": "PCD can build the 'Right Now' narrative.",
        "proprietary_penalty_applied": True,
    }
    report = GatekeeperReport.model_validate(data)
    assert report.total_score == 22
    assert report.classification.value == "high_potential_aspiring"


def test_gatekeeper_report_invalid_score():
    data = {
        "fund_name": "Bad Fund",
        "coiled_spring": {"score": 15, "diagnostic": "Too high"},
        "inbound_gravity": {"score": 5, "diagnostic": "Fine"},
        "outbound_mechanics": {"score": 5, "diagnostic": "Fine"},
        "logic_discipline": {"score": 5, "diagnostic": "Fine"},
        "total_score": 30,
        "classification": "native",
        "critical_flaw": "None",
        "pcd_intervention_viable": True,
        "pcd_intervention_detail": "Yes",
    }
    with pytest.raises(Exception):
        GatekeeperReport.model_validate(data)


def test_analyst_extraction_with_gaps():
    data = {
        "fund_name": "Test Fund",
        "executive_summary": "A focused growth equity fund.",
        "market_definition": None,
        "strategic_focus": "Lower mid-market healthcare services",
        "information_gaps": ["Market sizing not provided", "No historical track record data"],
        "required_interview_questions": ["What is your cost of capital logic?"],
    }
    extraction = AnalystExtraction.model_validate(data)
    assert len(extraction.information_gaps) == 2
    assert extraction.market_definition is None


def test_angle_brief_valid():
    data = {
        "gatekeeper_context": {
            "classification": "Native",
            "assertiveness_guidance": "Confident framing acceptable.",
            "should_generate_outreach": True,
        },
        "primary_angle": "differentiated_edge",
        "angle_rationale": "The GP's sourcing mechanism is the clearest LP-relevant point.",
        "top_points_to_surface": ["Point 1", "Point 2", "Point 3"],
        "points_to_avoid_or_deemphasize": ["Avoid hype"],
        "forwardable_sentence_goal": "One sentence an LP could forward.",
        "recommended_cta_type": "offer_deck",
        "subject_line_direction": "Lead with strategy niche.",
        "tone_guidance_for_gem3": "Measured confidence.",
        "constraints_for_gem3": ["No buzzwords", "No urgency overstatement"],
    }
    brief = AngleBrief.model_validate(data)
    assert brief.primary_angle.value == "differentiated_edge"


def test_gem3_emails_must_have_4():
    data = {
        "fund_name": "Test Fund",
        "emails": [
            {
                "label": "Fit/Relevance",
                "subject_a": "Subject A",
                "subject_b": "Subject B",
                "body": "Email body text here.",
                "word_count": 95,
                "angle": "fit",
            }
        ],
    }
    with pytest.raises(Exception):
        GEM3Emails.model_validate(data)


def test_deal_card_valid():
    data = {
        "fund_name": "Test Fund",
        "strategy_tag": "Growth Equity — Healthcare Services",
        "target_fund_size": "US$250M",
        "geography": "North America",
        "as_of_date": "29 03 2026",
        "right_now_window": {
            "dislocation": "Regulatory change creating consolidation window.",
            "catalyst": "Window closes in 18 months as incumbents adjust.",
        },
        "sourcing_forensics": {
            "receipts": "70% of deals sourced bilaterally.",
            "mechanism": "Proprietary clinical network of 200+ providers.",
        },
        "logic_discipline": {
            "cost_of_capital": "Target 3x MOIC minimum.",
            "binding_constraints": "No deals outside core geography. No pre-revenue.",
            "discipline_evidence": "Passed on 3 deals in 2025 that met financial criteria but failed ops check.",
        },
        "track_record": {
            "performance": "Fund II: 2.4x Gross MOIC, 28% Net IRR",
            "fund_terms": "2% Management Fee / 20% Carry / US$10-25M check size",
        },
        "action_cta": "Request the Full Manager Deck",
    }
    card = DealCard.model_validate(data)
    assert card.target_fund_size == "US$250M"


def test_cross_gem_eval_valid():
    data = {
        "overall_pass": False,
        "checks": {
            "strategy_drift": {"detected": True, "detail": "Email 2 describes a different market focus."},
            "urgency_drift": {"detected": False},
            "sourcing_edge_drift": {"detected": False},
            "unsupported_claims": {"detected": True, "detail": "Deal card cites a figure not in analyst report."},
            "formatting_violations": {"detected": False},
            "classification_misalignment": {"detected": False},
        },
        "artifacts_requiring_repair": ["gem3_randy_emails", "gem5_deal_card"],
        "decision": "revise",
        "revision_instructions": "Fix strategy description in Email 2. Remove unverified figure from deal card.",
    }
    eval_output = CrossGEMEvalOutput.model_validate(data)
    assert not eval_output.overall_pass
    assert len(eval_output.artifacts_requiring_repair) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
