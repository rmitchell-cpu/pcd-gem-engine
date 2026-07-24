"""
Step 1 — Prescreen Intake Report renderer.

Reads prescreen.json and produces the full Step 1 section:
  - Step heading
  - Metadata strip
  - Section 1: Scoring Assessment (table + per-pillar diagnostic prose)
  - Pillar Diagnostics banner
  - Per-pillar subsection headings + diagnostic paragraphs
  - Optional proprietary-penalty footnote
  - Verdict callout (tier headline + intervention detail)
  - Section 2: Gap Analysis & Recommended Next Steps
  - Hard page break to next step
"""

from datetime import datetime

from ..formatters import date_caps, tier_display
from ..styles import (
    add_callout_box, add_lead_in_paragraph, add_page_break,
    add_scoring_table, add_section_banner, add_section_heading,
    add_step_heading, add_subsection_heading, style_run,
)


# Pillar key -> long display name (used in scoring table).
PILLAR_LONG_NAMES = {
    "coiled_spring":      "Pillar 1 — The Coiled Spring (Right Now Argument)",
    "inbound_gravity":    "Pillar 2 — Inbound Gravity (Earned Advantage)",
    "outbound_mechanics": "Pillar 3 — Outbound Mechanics (Process Chain)",
    "logic_discipline":   "Pillar 4 — Logic & Discipline (No Framework)",
}

# Pillar key -> short display name (used in subsection headings).
PILLAR_SHORT_NAMES = {
    "coiled_spring":      "Pillar 1 — The Coiled Spring",
    "inbound_gravity":    "Pillar 2 — Inbound Gravity",
    "outbound_mechanics": "Pillar 3 — Outbound Mechanics",
    "logic_discipline":   "Pillar 4 — Logic & Discipline",
}

PILLAR_KEYS = ["coiled_spring", "inbound_gravity", "outbound_mechanics", "logic_discipline"]


def render(doc, *, prescreen, fund_name, as_of_date=None):
    """Render Step 1 — Prescreen Intake Report into `doc`."""
    if as_of_date is None:
        as_of_date = datetime.now()

    # --- Step heading (large navy bold) ----------------------------------
    add_step_heading(doc, "STEP 1 — PRESCREEN INTAKE REPORT")

    # Handle the missing-artifact case explicitly.
    if prescreen is None:
        doc.add_paragraph("[Stage Not Run — Artifact Not Available]")
        add_page_break(doc)
        return

    # --- Metadata strip --------------------------------------------------
    add_callout_box(
        doc,
        [f"PCD Intake Report  │  {fund_name}  │  {date_caps(as_of_date)}"],
    )

    doc.add_paragraph()  # spacer

    # --- Section 1: Scoring Assessment ----------------------------------
    add_section_heading(doc, "1. Scoring Assessment")

    rows = []
    for key in PILLAR_KEYS:
        pillar = prescreen.get(key) or {}
        score = pillar.get("score", "?")
        rows.append((PILLAR_LONG_NAMES[key], f"{score} / 10"))
    total_score = prescreen.get("total_score", "?")
    rows.append(("TOTAL", f"{total_score} / 40"))

    add_scoring_table(doc, rows)

    doc.add_paragraph()  # spacer

    # --- Pillar Diagnostics banner --------------------------------------
    add_section_banner(doc, "Pillar Diagnostics")

    # --- Per-pillar subsections -----------------------------------------
    for key in PILLAR_KEYS:
        pillar = prescreen.get(key) or {}
        score = pillar.get("score", "?")
        diagnostic = pillar.get("diagnostic", "[No diagnostic provided]")

        add_subsection_heading(doc, f"{PILLAR_SHORT_NAMES[key]} ({score}/10)")
        doc.add_paragraph(diagnostic)

    # --- Optional proprietary-penalty footnote --------------------------
    if prescreen.get("proprietary_penalty_applied"):
        para = doc.add_paragraph()
        run = para.add_run(
            "Note: Proprietary Penalty applied to Pillar 2 — the deck used "
            "‘proprietary’ to describe deal flow without showing the underlying "
            "mechanism. Two points deducted from Inbound Gravity."
        )
        style_run(run, italic=True)

    doc.add_paragraph()  # spacer

    # --- Verdict callout ------------------------------------------------
    classification = prescreen.get("classification", "")
    intervention_viable = bool(prescreen.get("pcd_intervention_viable", False))
    intervention_detail = prescreen.get("pcd_intervention_detail", "")

    tier_label = tier_display(classification).upper()
    verdict_lines = [f"TOTAL SCORE: {total_score}/40 — {tier_label}"]
    if intervention_detail:
        prefix = "Verdict:" if intervention_viable else "Decline:"
        verdict_lines.append(f"{prefix} {intervention_detail}")

    add_callout_box(doc, verdict_lines, bold_first=True)

    doc.add_paragraph()  # spacer

    # --- Section 2: Gap Analysis ----------------------------------------
    add_section_heading(doc, "2. Gap Analysis & Recommended Next Steps")

    critical_flaw = prescreen.get("critical_flaw") or "None identified."
    add_lead_in_paragraph(doc, "Critical Gap:", critical_flaw)

    intervention_label = "Yes" if intervention_viable else "No"
    add_lead_in_paragraph(doc, "PCD Intervention Viable?:", intervention_label)

    # --- Page break to Step 2 ------------------------------------------
    add_page_break(doc)
