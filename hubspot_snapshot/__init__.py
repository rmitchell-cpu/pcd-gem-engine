"""HubSpot marketing-email daily-snapshot artifact generator.

Pulls the last 30 days of marketing-email send statistics from the HubSpot
Marketing Email API, groups sends by day, computes per-email open / click /
CTOR / bounce / unsub rates (plus raw counts), builds a rollup KPI header with
trend vs. the prior 30-day period, renders a self-contained, sortable /
filterable, point-in-time-stamped HTML artifact, and verifies the rolled-up
numbers against the API aggregate before finishing.

Entry point: ``python -m hubspot_snapshot`` (see :mod:`hubspot_snapshot.cli`).
"""

from .metrics import (
    compute_rates,
    daily_groups,
    email_row,
    rollup,
    trend,
)
from .verify import verify_against_api

__all__ = [
    "compute_rates",
    "email_row",
    "daily_groups",
    "rollup",
    "trend",
    "verify_against_api",
]
