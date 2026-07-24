"""
Step 2 — Deck Analysis Report renderer.

Reads 02_deck_analysis.json and produces the full Step 2 section, the densest
analytical block in the report. Mirrors the legacy 650 Fund II layout while
honoring the new schema:
  - Step heading
  - Executive Summary callout
  - Section 1 — Market & Focus (Market Definition, Strategic Focus, Context Mastery)
  - Section 2 — The Opportunity (Recurring Patterns, Value Creation)
  - Section 3 — The Right Now Argument (Coiled Spring, Cyclical Awareness)
  - Section 4 — Sourcing Forensics (4A Inbound Gravity, 4B Outbound Mechanics)
  - Section 5 — Track Record Assessment (from red_flags.track_record_ambiguity)
  - Section 6 — Logic & Discipline (3-row Element/Finding table)
  - Section 7 — Red Flags (Key Person Risk, Fee Structure)
  - Questions for the GP (bulleted list)
  - Information Gaps (bulleted list — new section, not in legacy 650)
  - Hard page break to next step
"""

from ..styles import (
    add_bullet_list, add_callout_box, add_lead_in_paragraph, add_page_break,
    add_section_banner, add_step_heading, add_subsection_heading,
    add_two_column_text_table,
)


# Sentinel returned by the deck analysis stage when a field is absent.
NA = "[Information Not Available in Deck]"


def _safe(d, key, default=NA):
    """Return d[key] if it's a non-empty string, else default."""
    v = (d or {}).get(key)
    if isinstance(v, str) and v.strip():
        return v
    return default


def render(doc, *, deck_analysis, fund_name):
    """Render Step 2 — Deck Analysis Report into `doc`."""
    add_step_heading(doc, "STEP 2 — DECK ANALYSIS REPORT")

    if deck_analysis is None:
        doc.add_paragraph("[Stage Not Run — Artifact Not Available]")
        add_page_break(doc)
        return

    # --- Executive Summary callout --------------------------------------
    exec_summary = _safe(deck_analysis, "executive_summary")
    add_callout_box(
        doc,
        ["Executive Summary", exec_summary],
        bold_first=True,
    )
    doc.add_paragraph()  # spacer

    # --- Section 1 — Market & Focus -------------------------------------
    add_section_banner(doc, "Section 1 — Market & Focus")
    add_subsection_heading(doc, "Market Definition")
    doc.add_paragraph(_safe(deck_analysis, "market_definition"))
    add_subsection_heading(doc, "Strategic Focus")
    doc.add_paragraph(_safe(deck_analysis, "strategic_focus"))
    add_subsection_heading(doc, "Context Mastery")
    doc.add_paragraph(_safe(deck_analysis, "context_mastery"))
    doc.add_paragraph()

    # --- Section 2 — The Opportunity ------------------------------------
    add_section_banner(doc, "Section 2 — The Opportunity")
    add_subsection_heading(doc, "Recurring Patterns")
    doc.add_paragraph(_safe(deck_analysis, "recurring_patterns"))
    add_subsection_heading(doc, "Value Creation")
    doc.add_paragraph(_safe(deck_analysis, "value_creation"))
    doc.add_paragraph()

    # --- Section 3 — The Right Now Argument -----------------------------
    add_section_banner(doc, "Section 3 — The Right Now Argument")
    add_subsection_heading(doc, "The Coiled Spring")
    doc.add_paragraph(_safe(deck_analysis, "coiled_spring"))
    add_subsection_heading(doc, "Cyclical Awareness")
    doc.add_paragraph(_safe(deck_analysis, "cyclical_awareness"))
    doc.add_paragraph()

    # --- Section 4 — Sourcing Forensics ---------------------------------
    add_section_banner(doc, "Section 4 — Sourcing Forensics")
    inbound = deck_analysis.get("inbound_gravity") or {}
    outbound = deck_analysis.get("outbound_mechanics") or {}

    add_subsection_heading(doc, "4A — Inbound Gravity")
    add_lead_in_paragraph(doc, "Claim:", _safe(inbound, "claim"))
    add_lead_in_paragraph(doc, "Receipts:", _safe(inbound, "receipts"))

    add_subsection_heading(doc, "4B — Outbound Mechanics")
    add_lead_in_paragraph(doc, "Chain:", _safe(outbound, "chain"))
    add_lead_in_paragraph(doc, "Intersection:", _safe(outbound, "intersection"))
    add_lead_in_paragraph(doc, "Why They Win:", _safe(outbound, "why_they_win"))
    doc.add_paragraph()

    # --- Section 5 — Track Record Assessment ----------------------------
    # Legacy 650 had this as its own field; new schema folds it into red_flags.
    add_section_banner(doc, "Section 5 — Track Record Assessment")
    red_flags = deck_analysis.get("red_flags") or {}
    doc.add_paragraph(_safe(red_flags, "track_record_ambiguity"))
    doc.add_paragraph()

    # --- Section 6 — Logic & Discipline (3-row table) -------------------
    add_section_banner(doc, "Section 6 — Logic & Discipline")
    logic = deck_analysis.get("logic_discipline") or {}
    add_two_column_text_table(
        doc,
        ("Element", "Finding"),
        [
            ("Cost of Capital",     _safe(logic, "cost_of_capital")),
            ("Binding Constraints", _safe(logic, "binding_constraints")),
            ("Discipline Evidence", _safe(logic, "hard_no_story")),
        ],
    )
    doc.add_paragraph()

    # --- Section 7 — Red Flags ------------------------------------------
    add_section_banner(doc, "Section 7 — Red Flags")
    add_subsection_heading(doc, "Key Person Risk")
    doc.add_paragraph(_safe(red_flags, "key_person_risk"))
    add_subsection_heading(doc, "Fee Structure")
    doc.add_paragraph(_safe(red_flags, "fee_structure"))
    doc.add_paragraph()

    # --- Questions for the GP -------------------------------------------
    add_section_banner(doc, "Questions for the GP")
    questions = deck_analysis.get("required_interview_questions") or []
    questions = [q for q in questions if isinstance(q, str) and q.strip()]
    if questions:
        add_bullet_list(doc, questions)
    else:
        doc.add_paragraph("[No interview questions identified.]")
    doc.add_paragraph()

    # --- Information Gaps -----------------------------------------------
    add_section_banner(doc, "Information Gaps")
    gaps = deck_analysis.get("information_gaps") or []
    gaps = [g for g in gaps if isinstance(g, str) and g.strip()]
    if gaps:
        add_bullet_list(doc, gaps)
    else:
        doc.add_paragraph("[No information gaps identified.]")

    # --- Page break to Step 3 ------------------------------------------
    add_page_break(doc)
