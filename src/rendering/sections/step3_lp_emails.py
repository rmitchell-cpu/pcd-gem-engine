"""
Step 3 — LP Email Variants renderer.

Reads 06_lp_emails.json (the four email drafts) and 03_angle_brief.json (the
internal strategic positioning brief) and produces Step 3:
  - Step heading
  - Intro callout describing what's in this section
  - Per-email block (4 emails): banner with angle label, subject lines,
    light-blue callout box containing the email body, word count footnote
  - Internal subsection banner: 'Angle Brief — Internal PCD Use Only'
  - Angle Brief details (primary angle, rationale, top points, points to avoid,
    forwardable sentence goal, CTA type, tone guidance, constraints)
  - Hard page break to next step

The Angle Brief subsection mirrors the legacy 650 report's 'Drafting Notes —
Internal PCD Use Only' footer, but is now sourced from the Stage 03 artifact
rather than embedded in the LP emails skill.
"""

from ..styles import (
    NAVY, SIZE_BODY, WHITE,
    add_bullet_list, add_callout_box, add_lead_in_paragraph, add_page_break,
    add_section_banner, add_step_heading, add_subsection_heading,
    set_cell_shading, style_run,
)


# Angle key from JSON -> long display label.
# Email-level angles (per 06_lp_emails schema) use short keys: fit/edge/proof/followup.
# Angle-brief primary_angle (per 03_angle_brief schema) uses long keys.
ANGLE_DISPLAY = {
    # Email-level (06_lp_emails)
    "fit": "Fit / Relevance Angle",
    "edge": "Differentiated Edge Angle",
    "proof": "Proof / Repeatability Angle",
    "followup": "Short Forwardable Summary",
    # Angle-brief level (03_angle_brief)
    "fit_relevance": "Fit / Relevance Angle",
    "differentiated_edge": "Differentiated Edge Angle",
    "proof_repeatability": "Proof / Repeatability Angle",
    "right_now_timing": "Right Now Timing Angle",
    "short_forwardable_summary": "Short Forwardable Summary",
}

# CTA key from JSON -> human-readable description.
CTA_DISPLAY = {
    "fit_check": "Fit Check — invite the LP to self-qualify against allocation framework.",
    "offer_summary": "Offer Summary — provide a one-page summary if useful.",
    "offer_deck": "Offer Deck — share the full deck if LP wants a closer look.",
    "redirect_to_teammate": "Redirect to Teammate — connect to a PCD colleague who owns this space.",
    "offer_intro_if_useful": "Offer Intro — facilitate an introduction to the GP team if helpful.",
}


def _safe(d, key, default=""):
    """Return d[key] if it's a non-empty string, else default."""
    v = (d or {}).get(key)
    if isinstance(v, str) and v.strip():
        return v
    return default


def _render_email(doc, email):
    """Render a single email block: angle banner, subjects, body callout, word count."""
    angle = email.get("angle", "")
    label = email.get("label") or ANGLE_DISPLAY.get(angle, "Email")

    # Angle banner.
    add_section_banner(doc, label)

    # Subject line — primary (subject_a).
    subject_a = email.get("subject_a", "").strip()
    subject_b = email.get("subject_b", "").strip()

    if subject_a:
        add_lead_in_paragraph(doc, "Subject:", subject_a)
    if subject_b:
        # Show the alternate subject as a small italic note under the primary.
        para = doc.add_paragraph()
        run = para.add_run(f"Alternate subject: {subject_b}")
        style_run(run, size=SIZE_BODY - 1, italic=True)

    # Body — light-blue callout, mirroring the email's visual presentation in
    # the legacy report.
    body = _safe(email, "body", "[Email body missing]")
    add_callout_box(doc, [body])

    # Word count footnote.
    wc = email.get("word_count")
    if isinstance(wc, int) and wc > 0:
        para = doc.add_paragraph()
        run = para.add_run(f"Word count: {wc}")
        style_run(run, size=SIZE_BODY - 1, italic=True)

    doc.add_paragraph()  # spacer between emails


def _render_angle_brief(doc, angle_brief):
    """Render the internal-use angle brief subsection at the bottom of Step 3."""
    add_section_banner(doc, "Angle Brief — Internal PCD Use Only")

    # --- Prescreen context summary -------------------------------------
    ctx = angle_brief.get("prescreen_context") or {}
    classification = _safe(ctx, "classification")
    if classification:
        add_lead_in_paragraph(doc, "Classification:", classification)
    assertiveness = _safe(ctx, "assertiveness_guidance")
    if assertiveness:
        add_lead_in_paragraph(doc, "Assertiveness:", assertiveness)

    # --- Primary angle + rationale -------------------------------------
    primary_angle = _safe(angle_brief, "primary_angle")
    primary_label = ANGLE_DISPLAY.get(primary_angle, primary_angle or "[not specified]")
    add_lead_in_paragraph(doc, "Primary Angle:", primary_label)

    rationale = _safe(angle_brief, "angle_rationale")
    if rationale:
        add_lead_in_paragraph(doc, "Rationale:", rationale)

    # --- Top points to surface -----------------------------------------
    top_points = angle_brief.get("top_points_to_surface") or []
    top_points = [p for p in top_points if isinstance(p, str) and p.strip()]
    if top_points:
        add_subsection_heading(doc, "Top Points to Surface")
        add_bullet_list(doc, top_points)

    # --- Points to avoid -----------------------------------------------
    avoid = angle_brief.get("points_to_avoid_or_deemphasize") or []
    avoid = [p for p in avoid if isinstance(p, str) and p.strip()]
    if avoid:
        add_subsection_heading(doc, "Points to Avoid or De-emphasize")
        add_bullet_list(doc, avoid)

    # --- Forwardable sentence goal -------------------------------------
    fwd_goal = _safe(angle_brief, "forwardable_sentence_goal")
    if fwd_goal:
        add_subsection_heading(doc, "Forwardable Sentence Goal")
        doc.add_paragraph(fwd_goal)

    # --- Recommended CTA -----------------------------------------------
    cta_key = _safe(angle_brief, "recommended_cta_type")
    if cta_key:
        cta_text = CTA_DISPLAY.get(cta_key, cta_key)
        add_lead_in_paragraph(doc, "Recommended CTA:", cta_text)

    # --- Subject line direction ----------------------------------------
    subj_dir = _safe(angle_brief, "subject_line_direction")
    if subj_dir:
        add_lead_in_paragraph(doc, "Subject Line Direction:", subj_dir)

    # --- Tone guidance -------------------------------------------------
    tone = _safe(angle_brief, "tone_guidance")
    if tone:
        add_lead_in_paragraph(doc, "Tone Guidance:", tone)

    # --- Hard constraints ----------------------------------------------
    constraints = angle_brief.get("constraints") or []
    constraints = [c for c in constraints if isinstance(c, str) and c.strip()]
    if constraints:
        add_subsection_heading(doc, "Hard Constraints")
        add_bullet_list(doc, constraints)


def render(doc, *, lp_emails, angle_brief, fund_name):
    """Render Step 3 — LP Email Variants into `doc`."""
    add_step_heading(doc, "STEP 3 — LP EMAIL VARIANTS")

    # Intro callout explaining what's in this section.
    add_callout_box(
        doc,
        [
            f"Four LP introduction email variants for {fund_name}, each taking a "
            f"distinct angle. All emails follow Randy's voice profile: formal, "
            f"low-hype, LP-relevance first, and free of agency branding. The "
            f"angle brief at the end of this section documents PCD's internal "
            f"positioning logic and constraints used to draft them."
        ],
    )
    doc.add_paragraph()

    # Handle missing-artifact case.
    if lp_emails is None:
        doc.add_paragraph("[Stage Not Run — LP Emails Artifact Not Available]")
        add_page_break(doc)
        return

    # --- Render the four emails -----------------------------------------
    emails = lp_emails.get("emails") or []
    if not emails:
        doc.add_paragraph("[No email drafts present in artifact.]")
    else:
        for email in emails:
            _render_email(doc, email)

    # --- Render the angle brief subsection -----------------------------
    if angle_brief:
        _render_angle_brief(doc, angle_brief)
    else:
        doc.add_paragraph()
        add_section_banner(doc, "Angle Brief — Internal PCD Use Only")
        doc.add_paragraph("[Angle Brief Artifact Not Available]")

    # --- Page break to Step 4 ------------------------------------------
    add_page_break(doc)
