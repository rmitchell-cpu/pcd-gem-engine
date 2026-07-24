"""
Appendix — Pipeline Evaluation renderer.

Reads eval_voice.json and eval_cross_stage.json (both optional) and produces
an internal-use appendix showing pass/revise verdicts and per-check status.
This appendix is for PCD-internal trust signals (proof the pipeline's QA
gates ran clean), not customer-facing content.

Default-on behavior: appendix renders if either artifact is present.
Suppressed via --no-evals on the CLI.
"""

from ..styles import (
    LIGHT_BLUE, NAVY, SIZE_BODY,
    add_callout_box, add_lead_in_paragraph, add_page_break,
    add_section_banner, add_step_heading, add_subsection_heading,
    add_multi_column_text_table, set_cell_shading, style_run,
)


# Display labels for the six cross-stage checks.
CROSS_STAGE_CHECK_LABELS = {
    "strategy_drift":            "Strategy Drift",
    "urgency_drift":             "Urgency Drift",
    "sourcing_edge_drift":       "Sourcing / Edge Drift",
    "unsupported_claims":        "Unsupported Claims",
    "formatting_violations":     "Formatting Violations",
    "classification_misalignment": "Classification Misalignment",
}


def _safe(d, key, default=""):
    v = (d or {}).get(key)
    if isinstance(v, str) and v.strip():
        return v
    return default


def _render_voice_eval(doc, eval_voice):
    """Render the Voice Evaluation block."""
    add_section_banner(doc, "Voice Evaluation")

    decision = _safe(eval_voice, "decision", "[no decision]").upper()
    overall_pass = bool(eval_voice.get("overall_pass"))
    headline = f"DECISION: {decision}"
    if overall_pass:
        headline += "  —  All emails cleared voice criteria."
    add_callout_box(doc, [headline], bold_first=True)
    doc.add_paragraph()

    # --- Per-email score table ------------------------------------------
    emails = eval_voice.get("emails_evaluated") or []
    if emails:
        rows = []
        for e in emails:
            label = _safe(e, "label", "—")
            voice = e.get("voice_score", "—")
            lp_rel = e.get("lp_relevance_score", "—")
            cta = e.get("cta_quality_score", "—")
            fwd = e.get("forwardability_score", "—")
            overall = e.get("overall_score", "—")
            issues_count = len(e.get("issues") or [])
            rows.append([
                label,
                str(voice), str(lp_rel), str(cta), str(fwd), str(overall),
                str(issues_count),
            ])

        add_subsection_heading(doc, "Per-Email Scores")
        add_multi_column_text_table(
            doc,
            headers=("Email", "Voice", "LP Rel", "CTA", "Fwd", "Overall", "Issues"),
            rows=rows,
            column_widths_inches=[2.0, 0.7, 0.7, 0.7, 0.7, 0.85, 0.85],
        )

        # Issue detail subsection if any email has issues.
        emails_with_issues = [e for e in emails if e.get("issues")]
        if emails_with_issues:
            add_subsection_heading(doc, "Issue Detail")
            for e in emails_with_issues:
                label = _safe(e, "label", "—")
                add_lead_in_paragraph(doc, f"{label}:", "")
                for issue in e["issues"]:
                    if isinstance(issue, str) and issue.strip():
                        doc.add_paragraph(f"  • {issue}")
                if e.get("revision_instructions"):
                    add_lead_in_paragraph(
                        doc, "Revision Instructions:",
                        e["revision_instructions"],
                    )

    # --- Revision summary if revise verdict ----------------------------
    revision_summary = eval_voice.get("revision_summary")
    if isinstance(revision_summary, str) and revision_summary.strip():
        add_subsection_heading(doc, "Revision Summary")
        doc.add_paragraph(revision_summary)

    doc.add_paragraph()


def _render_cross_stage_eval(doc, eval_cross_stage):
    """Render the Cross-Stage Consistency Evaluation block."""
    add_section_banner(doc, "Cross-Stage Consistency Evaluation")

    decision = _safe(eval_cross_stage, "decision", "[no decision]").upper()
    overall_pass = bool(eval_cross_stage.get("overall_pass"))
    headline = f"DECISION: {decision}"
    if overall_pass:
        headline += "  —  No drift or violations detected."
    add_callout_box(doc, [headline], bold_first=True)
    doc.add_paragraph()

    # --- Six-check status table ----------------------------------------
    checks = eval_cross_stage.get("checks") or {}
    rows = []
    for key, label in CROSS_STAGE_CHECK_LABELS.items():
        check = checks.get(key) or {}
        detected = bool(check.get("detected"))
        status = "FLAGGED" if detected else "Pass"
        detail = check.get("detail") if detected else "—"
        if not isinstance(detail, str) or not detail.strip():
            detail = "—"
        rows.append([label, status, detail])

    add_subsection_heading(doc, "Six-Check Status")
    add_multi_column_text_table(
        doc,
        headers=("Check", "Status", "Detail"),
        rows=rows,
        column_widths_inches=[2.0, 1.0, 3.5],
    )

    # --- Artifacts requiring repair ------------------------------------
    repair = eval_cross_stage.get("artifacts_requiring_repair") or []
    repair = [r for r in repair if isinstance(r, str) and r.strip()]
    if repair:
        add_subsection_heading(doc, "Artifacts Requiring Repair")
        for r in repair:
            doc.add_paragraph(f"  • {r}")

    # --- Revision instructions if revise verdict -----------------------
    revision_instructions = eval_cross_stage.get("revision_instructions")
    if isinstance(revision_instructions, str) and revision_instructions.strip():
        add_subsection_heading(doc, "Revision Instructions")
        doc.add_paragraph(revision_instructions)


def render(doc, *, eval_voice, eval_cross_stage):
    """Render the Appendix — Pipeline Evaluation block into `doc`."""
    # Skip the appendix entirely if neither eval is present.
    if eval_voice is None and eval_cross_stage is None:
        return

    add_step_heading(doc, "APPENDIX — PIPELINE EVALUATION")

    add_callout_box(
        doc,
        [
            "This appendix documents the QA gates that ran on this pipeline "
            "execution. It is internal to PCD and is not part of LP-facing "
            "content. The Voice Evaluation checks the Stage 06 LP emails "
            "against Randy's voice profile; the Cross-Stage Consistency "
            "Evaluation checks downstream artifacts (Deal Card, LP Emails) "
            "against upstream truth (Prescreen, Deck Analysis, Angle Brief)."
        ],
    )
    doc.add_paragraph()

    if eval_voice is not None:
        _render_voice_eval(doc, eval_voice)
    if eval_cross_stage is not None:
        _render_cross_stage_eval(doc, eval_cross_stage)

    # No page break at end — appendix is the final section.
