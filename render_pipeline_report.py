"""
Pipeline Report Renderer — Commit 10 (Final: Eval Appendix + SKILL.md)

CLI entry point for rendering pcd-gem-engine job artifacts into a Word document.

Commit 10 closes out punchlist item 21:
  - Optional Appendix — Pipeline Evaluation (Voice Eval + Cross-Stage Eval)
    rendered when either artifact is present. Suppressed via --no-evals.
  - SKILL.md sibling file makes the renderer discoverable to Claude Cowork
    when invoked with phrases like "render the pipeline report" or "build
    the Word doc from the artifacts."

Section dispatch is now complete: cover, Step 1 (Prescreen), Step 2 (Deck
Analysis), Step 3 (LP Emails + Angle Brief), Step 4 (Preqin Taxonomy),
Step 5 (Deal Card), Appendix (Voice Eval + Cross-Stage Eval).

Usage:
    Validate only (no render):
        ./.venv/bin/python render_pipeline_report.py \\
            --artifacts-dir <path> --validate-only

    Render with eval appendix (default):
        ./.venv/bin/python render_pipeline_report.py \\
            --artifacts-dir <path> --output <path-to-output.docx>

    Render without eval appendix:
        ./.venv/bin/python render_pipeline_report.py \\
            --artifacts-dir <path> --output <path-to-output.docx> --no-evals
"""

import argparse
import sys
from pathlib import Path

# Make src/ importable when running this script from the project root.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rendering.io import (
    REQUIRED_ARTIFACTS, inventory, report_validation,
)
from rendering.report_renderer import render_report


def main():
    parser = argparse.ArgumentParser(
        description="Render a pcd-gem-engine pipeline job into a Word document."
    )
    parser.add_argument(
        "--artifacts-dir",
        required=True,
        type=Path,
        help="Path to a jobs/<job_id>/artifacts/ folder",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination path for the .docx file (required when not --validate-only)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Do not render; just inspect the artifacts directory and report.",
    )
    parser.add_argument(
        "--no-evals",
        action="store_true",
        help="Suppress the Appendix — Pipeline Evaluation block, even when "
             "eval_voice.json or eval_cross_stage.json is present.",
    )
    args = parser.parse_args()

    artifacts_dir = args.artifacts_dir.expanduser().resolve()

    if not artifacts_dir.exists():
        print(f"ERROR: artifacts directory does not exist: {artifacts_dir}")
        sys.exit(1)
    if not artifacts_dir.is_dir():
        print(f"ERROR: path is not a directory: {artifacts_dir}")
        sys.exit(1)

    presence, actual_files = inventory(artifacts_dir)

    if args.validate_only:
        ok = report_validation(artifacts_dir, presence, actual_files)
        sys.exit(0 if ok else 1)

    # Rendering path: enforce required artifacts and require --output.
    required_missing = [f for f in REQUIRED_ARTIFACTS if not presence[f]]
    if required_missing:
        print(
            f"ERROR: cannot render — {len(required_missing)} required artifact(s) missing: "
            f"{', '.join(required_missing)}"
        )
        sys.exit(1)
    if args.output is None:
        print("ERROR: --output is required when not in --validate-only mode.")
        print("Example: --output ~/Desktop/Pipeline_Report.docx")
        sys.exit(1)

    written = render_report(
        artifacts_dir, args.output, presence,
        include_evals=not args.no_evals,
    )
    print(f"Wrote: {written}")
    print(f"Open with: open '{written}'")


if __name__ == "__main__":
    main()
