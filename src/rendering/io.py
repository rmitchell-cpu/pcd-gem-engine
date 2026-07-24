"""
Artifact loading and presence inventory.

Resolves the three-bucket model (REQUIRED, OPTIONAL, NOT_RENDERED) introduced
in Commit 2 and centralizes JSON parsing so section renderers don't each
re-implement file I/O.
"""

import json
from pathlib import Path


REQUIRED_ARTIFACTS = [
    "prescreen.json",
    "02_deck_analysis.json",
    "03_angle_brief.json",
    "04_preqin_taxonomy.json",
    "05_deal_card.json",
    "06_lp_emails.json",
]

OPTIONAL_ARTIFACTS = [
    "01_fund_extract.json",
    "eval_voice.json",
    "eval_cross_stage.json",
]

# Files known to exist in job folders but never rendered into the report.
# (parsed_deck.json is the raw deck text used as pipeline input — not output.)
NOT_RENDERED_ARTIFACTS = [
    "parsed_deck.json",
]


def inventory(artifacts_dir):
    """
    Inspect an artifacts directory and return:
      - presence: dict mapping every known artifact filename to True/False
      - actual_files: set of every filename actually present in the directory
    """
    actual_files = {p.name for p in artifacts_dir.iterdir() if p.is_file()}
    all_known = REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS + NOT_RENDERED_ARTIFACTS
    presence = {f: (f in actual_files) for f in all_known}
    return presence, actual_files


def load_json(artifacts_dir, filename):
    """
    Load a JSON file from the artifacts directory. Returns the parsed Python
    object, or None if the file is absent, unreadable, or malformed.
    """
    path = artifacts_dir / filename
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def report_validation(artifacts_dir, presence, actual_files):
    """
    Print the three-bucket validation summary used by --validate-only.
    Returns True if all required artifacts are present, False otherwise.
    """
    print(f"Inspecting: {artifacts_dir}")
    print()

    required_found = [f for f in REQUIRED_ARTIFACTS if presence[f]]
    optional_found = [f for f in OPTIONAL_ARTIFACTS if presence[f]]
    not_rendered_found = [f for f in NOT_RENDERED_ARTIFACTS if presence[f]]

    known_set = set(REQUIRED_ARTIFACTS) | set(OPTIONAL_ARTIFACTS) | set(NOT_RENDERED_ARTIFACTS)
    unknown = sorted(actual_files - known_set)

    print(f"REQUIRED ({len(required_found)} of {len(REQUIRED_ARTIFACTS)} found):")
    for f in REQUIRED_ARTIFACTS:
        marker = "[OK]" if presence[f] else "[MISSING]"
        print(f"  {marker} {f}")
    print()

    print(f"OPTIONAL ({len(optional_found)} of {len(OPTIONAL_ARTIFACTS)} found):")
    for f in OPTIONAL_ARTIFACTS:
        marker = "[OK]" if presence[f] else "[absent]"
        print(f"  {marker} {f}")
    print()

    if not_rendered_found:
        print(f"NOT RENDERED ({len(not_rendered_found)} present, will not appear in report):")
        for f in not_rendered_found:
            print(f"  [skip] {f}")
        print()

    if unknown:
        print(f"UNKNOWN ({len(unknown)} present, not classified):")
        for f in unknown:
            print(f"  [???] {f}")
        print()

    required_missing = [f for f in REQUIRED_ARTIFACTS if not presence[f]]
    if required_missing:
        print(f"VERDICT: incomplete — {len(required_missing)} required artifact(s) missing.")
        return False
    print("VERDICT: all required artifacts present.")
    return True
