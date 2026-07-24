"""
Format normalization for rendered output.

The pipeline's JSON artifacts are inconsistent about currency notation
(`$70-75MM` vs. `US$70-75M`) and date format (`31 03 2026` vs. natural
language). This module applies the canonical PCD style at render time:
  - Currency: US$, single 'M' suffix for millions.
  - Dates in headers/banners/metadata strips: ALL CAPS (e.g. '27 APRIL 2026').
  - Dates in prose: mixed case (e.g. '27 April 2026').

Long-term, normalization belongs upstream in the pipeline stages. Until then,
the renderer is the safety net.
"""

import re
from datetime import datetime


# --- Tier classification display ------------------------------------------

TIER_DISPLAY = {
    "native": "Native",
    "high_potential_aspiring": "High-Potential Aspiring",
    "challenging": "Challenging",
}


def tier_display(classification):
    """Map snake_case classification to Title-Case display string."""
    if not classification:
        return "[Tier Missing]"
    return TIER_DISPLAY.get(classification, classification)


# --- Date formatting ------------------------------------------------------

def date_caps(d):
    """'27 APRIL 2026' — used in header strips, metadata strips, banners."""
    return d.strftime("%d %B %Y").upper()


def date_mixed(d):
    """'27 April 2026' — used in prose."""
    return d.strftime("%d %B %Y")


def parse_pipeline_date(s):
    """
    Parse a date string from a pipeline artifact. Pipeline stages emit dates
    in '31 03 2026' format (DD MM YYYY space-separated). Falls back to None
    on any other format — caller is expected to handle.
    """
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s.strip(), "%d %m %Y")
    except ValueError:
        return None


# --- Currency normalization -----------------------------------------------

# Match common currency notations the pipeline emits:
#   $70MM, $70-75MM, USD 70M, US$70-75 million, etc.
# Goal: normalize to 'US$70-75M' style.
_CURRENCY_RE = re.compile(
    r"\b(?:US\$|USD\s*\$?|\$)\s*"
    r"(\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?)"
    r"\s*(MM|M|B|bn|million|billion)\b",
    flags=re.IGNORECASE,
)


def _normalize_currency_match(m):
    amount = m.group(1).replace(" ", "")
    unit_in = m.group(2).lower()
    unit_out = {
        "mm": "M",
        "m": "M",
        "million": "M",
        "b": "B",
        "bn": "B",
        "billion": "B",
    }.get(unit_in, unit_in.upper())
    return f"US${amount}{unit_out}"


def normalize_currency(text):
    """Rewrite currency tokens in `text` to canonical 'US$NM' / 'US$NB' form."""
    if not text or not isinstance(text, str):
        return text
    return _CURRENCY_RE.sub(_normalize_currency_match, text)
