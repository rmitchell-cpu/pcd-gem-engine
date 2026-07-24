"""
Step 4 — Preqin Taxonomy Translation renderer.

Reads 04_preqin_taxonomy.json and produces Step 4:
  - Step heading
  - § 1 Strategy Summary in Plain English (single paragraph)
  - § 2 Translation Matrix (5-column table)
  - § 3 Search Strategy Checklist (Verticals, Industries, Keywords as lists)
  - § 4 Boolean Search Strings (3 labeled callout boxes)
  - Canonical Strategy Tags footer (comma-separated)
  - Hard page break to next step
"""

from ..styles import (
    SIZE_BODY,
    add_bullet_list, add_callout_box, add_lead_in_paragraph,
    add_multi_column_text_table, add_page_break, add_section_banner,
    add_section_heading, add_step_heading, add_subsection_heading, style_run,
)


def _safe(d, key, default=""):
    v = (d or {}).get(key)
    if isinstance(v, str) and v.strip():
        return v
    return default


def render(doc, *, preqin_taxonomy):
    """Render Step 4 — Preqin Taxonomy Translation into `doc`."""
    add_step_heading(doc, "STEP 4 — PREQIN TAXONOMY TRANSLATION")

    if preqin_taxonomy is None:
        doc.add_paragraph("[Stage Not Run — Artifact Not Available]")
        add_page_break(doc)
        return

    # --- § 1 Strategy Summary in Plain English -------------------------
    add_section_heading(doc, "1. Strategy Summary in Plain English")
    summary = _safe(preqin_taxonomy, "strategy_summary",
                    "[Strategy summary not available]")
    doc.add_paragraph(summary)
    doc.add_paragraph()

    # --- § 2 Translation Matrix ----------------------------------------
    add_section_heading(doc, "2. Translation Matrix")
    matrix_rows = preqin_taxonomy.get("translation_matrix") or []

    if matrix_rows:
        rendered_rows = []
        for entry in matrix_rows:
            theme = _safe(entry, "fund_theme", "—")
            evidence = _safe(entry, "context_evidence", "—")
            primary = _safe(entry, "primary_match", "—")
            secondary_list = entry.get("secondary_matches") or []
            secondary = ", ".join(
                s for s in secondary_list if isinstance(s, str) and s.strip()
            ) or "—"
            type_label = _safe(entry, "type", "—")
            rendered_rows.append([theme, evidence, primary, secondary, type_label])

        add_multi_column_text_table(
            doc,
            headers=("Fund Theme", "Evidence", "Primary Match",
                     "Secondary Matches", "Type"),
            rows=rendered_rows,
            # Wider for evidence prose, narrower for type.
            column_widths_inches=[1.1, 2.0, 1.2, 1.5, 0.7],
        )
    else:
        doc.add_paragraph("[No translation matrix entries.]")

    doc.add_paragraph()

    # --- § 3 Search Strategy Checklist ---------------------------------
    add_section_heading(doc, "3. Search Strategy Checklist")
    search = preqin_taxonomy.get("search_strategy") or {}

    verticals = [v for v in (search.get("verticals") or []) if isinstance(v, str) and v.strip()]
    industries = [i for i in (search.get("industries") or []) if isinstance(i, str) and i.strip()]
    keywords = [k for k in (search.get("keywords") or []) if isinstance(k, str) and k.strip()]

    if verticals:
        add_subsection_heading(doc, "Verticals")
        add_bullet_list(doc, verticals)

    if industries:
        add_subsection_heading(doc, "Industries")
        add_bullet_list(doc, industries)

    if keywords:
        add_subsection_heading(doc, "Keywords")
        add_bullet_list(doc, keywords)

    if not (verticals or industries or keywords):
        doc.add_paragraph("[No search strategy elements specified.]")

    doc.add_paragraph()

    # --- § 4 Boolean Search Strings ------------------------------------
    add_section_heading(doc, "4. Boolean Search Strings")
    bools = preqin_taxonomy.get("boolean_strings") or {}

    string_definitions = [
        ("String 1 — Broad Thesis", "broad_thesis",
         "Maximum recall; surfaces all potentially relevant LPs."),
        ("String 2 — Niche / Deep Tech", "niche_deep_tech",
         "Precision targeting on the most distinctive positioning."),
        ("String 3 — Geography-Specific", "geo_specific",
         "Geography constraint layered onto the core thesis."),
    ]

    for label, key, use_case in string_definitions:
        add_subsection_heading(doc, label)
        boolean_str = _safe(bools, key, "[Not provided]")
        add_callout_box(
            doc,
            [boolean_str, f"Use case: {use_case}"],
            bold_first=True,
        )
        doc.add_paragraph()  # spacer between strings

    # --- Canonical Strategy Tags footer --------------------------------
    add_section_banner(doc, "Canonical Strategy Tags")
    tags = [t for t in (preqin_taxonomy.get("canonical_strategy_tags") or [])
            if isinstance(t, str) and t.strip()]
    if tags:
        para = doc.add_paragraph()
        run = para.add_run(" • ".join(tags))
        style_run(run, size=SIZE_BODY)
    else:
        doc.add_paragraph("[No canonical tags assigned.]")

    # --- Page break to Step 5 ------------------------------------------
    add_page_break(doc)
