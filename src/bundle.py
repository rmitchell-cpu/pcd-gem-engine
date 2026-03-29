"""Final review bundle assembly."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config.settings import JOBS_DIR
from src.models import (
    GatekeeperClassification,
    GatekeeperReport,
    ReviewBundleManifest,
    WorkflowState,
)
from src.persistence import load_manifest


def assemble_review_bundle(
    job_id: str,
    fund_name: str,
    gatekeeper: GatekeeperReport,
    evaluator_passed: bool,
    regeneration_count: int = 0,
) -> ReviewBundleManifest:
    """Assemble the final review bundle manifest.

    Scans the artifacts directory to build a complete inventory
    of what was produced during this pipeline run.
    """
    manifest = load_manifest(job_id)
    artifact_dir = JOBS_DIR / job_id / "artifacts"

    # Collect all artifacts
    artifacts: dict[str, str] = {}
    if artifact_dir.exists():
        for f in sorted(artifact_dir.iterdir()):
            if f.suffix == ".json" and f.name != "parsed_deck.json":
                artifacts[f.stem] = f"artifacts/{f.name}"

    # Determine flagged items
    flagged: list[str] = []
    manual_attention: list[str] = []

    if not evaluator_passed:
        flagged.append("Evaluators did not fully pass — review downstream artifacts carefully")

    if regeneration_count > 0:
        flagged.append(f"Regeneration was triggered {regeneration_count} time(s)")

    if gatekeeper.classification == GatekeeperClassification.TOURIST:
        manual_attention.append("Tourist classification — no LP outreach generated")
        flagged.append("Pipeline stopped at Gatekeeper — internal artifacts only")

    if gatekeeper.proprietary_penalty_applied:
        flagged.append("Proprietary penalty was applied to Inbound Gravity score")

    return ReviewBundleManifest(
        job_id=job_id,
        fund_name=fund_name,
        created_at=datetime.utcnow(),
        pipeline_status=manifest.current_state,
        gatekeeper_classification=gatekeeper.classification,
        gatekeeper_score=gatekeeper.total_score,
        evaluator_passed=evaluator_passed,
        regeneration_count=regeneration_count,
        artifacts=artifacts,
        flagged_items=flagged,
        requires_manual_attention=manual_attention,
    )


def generate_human_readable_summary(bundle: ReviewBundleManifest) -> str:
    """Generate a plain-text summary suitable for human review."""
    lines = [
        "=" * 60,
        "PCD GEM ENGINE — REVIEW BUNDLE",
        "=" * 60,
        "",
        f"Fund:           {bundle.fund_name}",
        f"Job ID:         {bundle.job_id}",
        f"Generated:      {bundle.created_at.strftime('%d %m %Y %H:%M UTC')}",
        f"Pipeline State: {bundle.pipeline_status.value}",
        "",
        "--- GATEKEEPER ---",
        f"Score:          {bundle.gatekeeper_score}/40",
        f"Classification: {bundle.gatekeeper_classification.value}",
        "",
        "--- EVALUATORS ---",
        f"Passed:         {'Yes' if bundle.evaluator_passed else 'NO — review required'}",
        f"Regen Rounds:   {bundle.regeneration_count}",
        "",
    ]

    if bundle.flagged_items:
        lines.append("--- FLAGS ---")
        for flag in bundle.flagged_items:
            lines.append(f"  ! {flag}")
        lines.append("")

    if bundle.requires_manual_attention:
        lines.append("--- MANUAL ATTENTION REQUIRED ---")
        for item in bundle.requires_manual_attention:
            lines.append(f"  >> {item}")
        lines.append("")

    lines.append("--- ARTIFACTS ---")
    for stage, path in sorted(bundle.artifacts.items()):
        lines.append(f"  {stage:30s} → {path}")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
