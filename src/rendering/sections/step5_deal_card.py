"""
Step 5 — Deal Card (Tear Sheet) renderer.

Reads 05_deal_card.json and produces the four-pillar LP-facing tear sheet:
  - Step heading
  - Dark-navy fund-name header callout with strategy/size/geography/date
  - The Right Now Window banner (Dislocation, Catalyst)
  - Sourcing Forensics banner (Receipts, Mechanism)
  - Logic & Discipline banner + 3-row table
  - Track Record & Key Terms banner (Performance, Fund Terms)
  - Action CTA callout
  - INTERNAL NOTE — PCD Use Only callout (composed from prescreen + deck
    analysis to give PCD-internal readers context the LP would not see)
  - Hard page break to next step
"""

from ..formatters import normalize_currency
from ..styles import (
    add_callout_box, add_lead_in_paragraph, add_navy_header_callout,
    add_page_break, add_section_banner, add_step_heading,
    add_two_column_text_table,
)


def _safe(d, key, default="[Data Not Disclosed]"):
    """Return d[key] if it's a non-empty string, else default."""
    v = (d or {}).get(key)
    if isinstance(v, str) and v.strip():
        return v
    return default


def _format_metadata_strip(deal_card):
    """Compose the metadata lines that sit under the navy fund-name title."""
    strategy = _safe(deal_card, "strategy_tag", "[Strategy not classified]")
    size = _safe(deal_card, "target_fund_size", "[Size not disclosed]")
    geography = _safe(deal_card, "geography", "[Geography not specified]")
    as_of = _safe(deal_card, "as_of_date", "")

    lines = [f"Strategy: {strategy}"]
    second_line_bits = [f"Target Fund Size: {size}", f"Geography: {geography}"]
    if as_of:
        second_line_bits.append(f"As of: {as_of}")
    lines.append("  •  ".join(second_line_bits))
    return lines


def _compose_internal_note(prescreen, deck_analysis):
    """
    Compose the INTERNAL NOTE — PCD Use Only block that closes the Deal Card.
    Pulls prescreen score and critical flaw, plus a brief excerpt of the top
    information gaps so PCD readers see what an LP would push on.
    """
    lines = []

    if prescreen:
        score = prescreen.get("total_score", "?")
        classification = prescreen.get("classification", "")
        tier_label = {
            "native": "Native",
            "high_potential_aspiring": "High-Potential Aspiring",
            "challenging": "Challenging",
        }.get(classification, classification or "—")
        lines.append(f"Prescreen: {score}/40 — {tier_label}")

        critical_flaw = prescreen.get("critical_flaw")
        if isinstance(critical_flaw, str) and critical_flaw.strip() and critical_flaw != "None identified.":
            lines.append(f"Critical Flaw: {critical_flaw}")

    if deck_analysis:
        gaps = deck_analysis.get("information_gaps") or []
        gaps = [g for g in gaps if isinstance(g, str) and g.strip()]
        if gaps:
            top_gaps = gaps[:3]  # Show first 3 only — keep the note concise
            lines.append("Top Information Gaps (LPs will press on these):")
            for g in top_gaps:
                lines.append(f"  • {g}")

    if not lines:
        lines = ["[No internal context available]"]
    return lines


def render(doc, *, deal_card, prescreen=None, deck_analysis=None):
    """Render Step 5 — Deal Card into `doc`."""
    add_step_heading(doc, "STEP 5 — DEAL CARD")

    if deal_card is None:
        doc.add_paragraph("[Stage Not Run — Artifact Not Available]")
        add_page_break(doc)
        return

    # --- Dark-navy fund-name header callout ----------------------------
    fund_name = _safe(deal_card, "fund_name", "[Fund Name Missing]")
    add_navy_header_callout(
        doc,
        title=fund_name,
        lines=_format_metadata_strip(deal_card),
    )
    doc.add_paragraph()

    # --- The Right Now Window ------------------------------------------
    add_section_banner(doc, "The Right Now Window")
    rnw = deal_card.get("right_now_window") or {}
    add_lead_in_paragraph(
        doc, "Dislocation:", normalize_currency(_safe(rnw, "dislocation"))
    )
    add_lead_in_paragraph(
        doc, "Catalyst:", normalize_currency(_safe(rnw, "catalyst"))
    )
    doc.add_paragraph()

    # --- Sourcing Forensics --------------------------------------------
    add_section_banner(doc, "Sourcing Forensics")
    sf = deal_card.get("sourcing_forensics") or {}
    add_lead_in_paragraph(
        doc, "Receipts:", normalize_currency(_safe(sf, "receipts"))
    )
    add_lead_in_paragraph(
        doc, "Mechanism:", normalize_currency(_safe(sf, "mechanism"))
    )
    doc.add_paragraph()

    # --- Logic & Discipline (3-row table) ------------------------------
    add_section_banner(doc, "Logic & Discipline")
    ld = deal_card.get("logic_discipline") or {}
    add_two_column_text_table(
        doc,
        ("Element", "Finding"),
        [
            ("Cost of Capital",     normalize_currency(_safe(ld, "cost_of_capital"))),
            ("Binding Constraints", normalize_currency(_safe(ld, "binding_constraints"))),
            ("Discipline Evidence", normalize_currency(_safe(ld, "discipline_evidence"))),
        ],
    )
    doc.add_paragraph()

    # --- Track Record & Key Terms --------------------------------------
    add_section_banner(doc, "Track Record & Key Terms")
    tr = deal_card.get("track_record") or {}
    add_lead_in_paragraph(
        doc, "Performance:", normalize_currency(_safe(tr, "performance"))
    )
    add_lead_in_paragraph(
        doc, "Fund Terms:", normalize_currency(_safe(tr, "fund_terms"))
    )
    doc.add_paragraph()

    # --- Action CTA ----------------------------------------------------
    add_section_banner(doc, "Action CTA")
    cta = _safe(deal_card, "action_cta")
    add_callout_box(doc, [cta])
    doc.add_paragraph()

    # --- INTERNAL NOTE — PCD Use Only ----------------------------------
    add_section_banner(doc, "INTERNAL NOTE — PCD Use Only")
    add_callout_box(
        doc,
        _compose_internal_note(prescreen, deck_analysis),
    )

    # --- Page break to Appendix ----------------------------------------
    add_page_break(doc)
