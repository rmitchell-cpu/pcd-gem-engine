#!/usr/bin/env python3
"""PCD GEM Engine — CLI entry point.

Usage:
    # Run the full pipeline on a deck
    python run.py path/to/deck.pdf

    # Rerun a single stage on an existing job
    python run.py --stage gem2_extractor --job 20260329_143012_abc12345

    # List all jobs
    python run.py --list-jobs

    # Show job status
    python run.py --status --job 20260329_143012_abc12345
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the engine root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import JOBS_DIR
from src.bundle import generate_human_readable_summary
from src.models import ReviewBundleManifest
from src.orchestrator import rerun_stage, run_pipeline
from src.persistence import list_jobs, load_manifest


def main():
    parser = argparse.ArgumentParser(
        description="PCD GEM Concierge Workflow Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("deck", nargs="?", help="Path to the GP fund manager deck (PDF)")
    parser.add_argument("--stage", help="Rerun a specific stage (requires --job)")
    parser.add_argument("--job", help="Job ID for single-stage rerun or status check")
    parser.add_argument("--list-jobs", action="store_true", help="List all pipeline jobs")
    parser.add_argument("--status", action="store_true", help="Show job status (requires --job)")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")

    args = parser.parse_args()

    # List jobs
    if args.list_jobs:
        jobs = list_jobs()
        if not jobs:
            print("No jobs found.")
            return
        print(f"{'Job ID':<35} {'Fund':<30} {'State':<25} {'Created'}")
        print("-" * 110)
        for j in jobs:
            fund = j.fund_name or "(unknown)"
            print(f"{j.job_id:<35} {fund:<30} {j.current_state.value:<25} {j.created_at.strftime('%d %m %Y %H:%M')}")
        return

    # Show status
    if args.status:
        if not args.job:
            print("ERROR: --status requires --job <job_id>")
            sys.exit(1)
        manifest = load_manifest(args.job)
        print(json.dumps(manifest.model_dump(), indent=2, default=str))

        # Show review bundle if it exists
        bundle_path = JOBS_DIR / args.job / "review_bundle.json"
        if bundle_path.exists():
            bundle = ReviewBundleManifest.model_validate_json(bundle_path.read_text())
            print()
            print(generate_human_readable_summary(bundle))
        return

    # Rerun a single stage
    if args.stage:
        if not args.job:
            print("ERROR: --stage requires --job <job_id>")
            sys.exit(1)
        print(f"Rerunning stage '{args.stage}' for job {args.job}...")
        result = rerun_stage(args.job, args.stage)
        if result.success:
            print(f"SUCCESS: {result.artifact_path}")
        else:
            print(f"FAILED: {result.error}")
            sys.exit(1)
        return

    # Full pipeline
    if not args.deck:
        parser.print_help()
        sys.exit(1)

    deck_path = Path(args.deck)
    if not deck_path.exists():
        print(f"ERROR: Deck file not found: {deck_path}")
        sys.exit(1)

    bundle_path = run_pipeline(str(deck_path), verbose=not args.quiet)

    # Print the human-readable summary
    if bundle_path and Path(bundle_path).exists():
        bundle = ReviewBundleManifest.model_validate_json(Path(bundle_path).read_text())
        print()
        print(generate_human_readable_summary(bundle))


if __name__ == "__main__":
    main()
