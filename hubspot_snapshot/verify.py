"""Verification: reconcile the artifact's numbers against the HubSpot API.

Two layers of checks:

1. **Internal consistency** — the per-day group counters must sum to the same
   totals as the flat per-email rollup. Catches grouping/aggregation bugs.

2. **API reconciliation** — our summed counters are compared against the
   account-wide aggregate returned by
   ``/marketing/v3/emails/statistics/list`` for the same window. Because the
   aggregate can include emails whose send date falls outside our 30-day
   send-day window (it aggregates *activity* in the window), the rollup is
   expected to be <= the aggregate; an exact match is reported when the
   endpoint scopes to the same email set. Recomputed rates are also checked
   against the API's own ratios within a tolerance.

Each check is returned with a pass/fail flag and the compared values so the
result can be rendered into the artifact and printed to the console.
"""

from __future__ import annotations

from typing import Any

from .client import extract_counters
from .metrics import COUNTER_KEYS, compute_rates, daily_groups, rollup

RATE_TOLERANCE = 0.005  # 0.5 percentage points


def _api_ratios(aggregate: dict[str, Any]) -> dict[str, float]:
    """Extract HubSpot's own ratio block (raw values, scale-agnostic).

    HubSpot has returned email ratios as both fractions (0-1) and percentages
    (0-100) across API versions, and a small percentage like ``0.51`` is
    ambiguous on its own. We return the raw number and let the caller resolve
    the scale against the independently-recomputed rate.
    """
    node = aggregate
    if isinstance(aggregate.get("aggregate"), dict):
        node = aggregate["aggregate"]
    if isinstance(node.get("statistics"), dict):
        node = node["statistics"]
    ratios = node.get("ratios", {}) if isinstance(node, dict) else {}

    def g(*keys: str) -> float | None:
        for key in keys:
            if key in ratios and ratios[key] is not None:
                try:
                    return float(ratios[key])
                except (TypeError, ValueError):
                    return None
        return None

    return {
        "open_rate": g("openratio", "openrate"),
        "click_rate": g("clickratio", "clickrate"),
        "ctor": g("clickthroughratio", "ctr"),
        "bounce_rate": g("bounceratio", "bouncerate"),
        "unsub_rate": g("unsubscribedratio", "unsubscriberatio"),
    }


def verify_against_api(
    rows: list[dict[str, Any]], api_aggregate: dict[str, Any] | None
) -> dict[str, Any]:
    """Run all verification checks and return a structured result."""
    checks: list[dict[str, Any]] = []

    our = rollup(rows)
    our_counters = our["counters"]

    # 1. Internal consistency: daily groups vs flat rollup.
    group_total = {k: 0 for k in COUNTER_KEYS}
    for grp in daily_groups(rows):
        for k in COUNTER_KEYS:
            group_total[k] += grp["counters"][k]
    internal_ok = all(group_total[k] == our_counters[k] for k in COUNTER_KEYS)
    checks.append(
        {
            "name": "Daily groups reconcile to rollup",
            "passed": internal_ok,
            "detail": "per-day counter sums == flat rollup"
            if internal_ok
            else f"mismatch: groups={group_total} rollup={our_counters}",
        }
    )

    # 2 & 3. API reconciliation (only when an aggregate is available).
    if api_aggregate:
        api_counters = extract_counters(api_aggregate)
        for k in COUNTER_KEYS:
            ours, theirs = our_counters[k], api_counters[k]
            # Rollup counts sends in our window; the API aggregate may span more.
            passed = ours == theirs or (theirs > 0 and ours <= theirs)
            checks.append(
                {
                    "name": f"Counter '{k}' vs API aggregate",
                    "passed": passed,
                    "detail": f"rollup={ours:,} api={theirs:,}"
                    + ("" if ours == theirs else " (rollup ⊆ window aggregate)"),
                }
            )

        api_rates = _api_ratios(api_aggregate)
        our_rates = compute_rates(our_counters)
        for key, raw in api_rates.items():
            if raw is None:
                continue
            our_val = our_rates[key]
            # Resolve fraction-vs-percentage by taking whichever scale is
            # closest to our independently-recomputed rate.
            api_val = min((raw, raw / 100.0), key=lambda v: abs(v - our_val))
            passed = abs(our_val - api_val) <= RATE_TOLERANCE
            checks.append(
                {
                    "name": f"Rate '{key}' vs API ratio",
                    "passed": passed,
                    "detail": f"recomputed={our_val*100:.2f}% api={api_val*100:.2f}% "
                    f"(tol {RATE_TOLERANCE*100:.1f}pp)",
                }
            )
    else:
        checks.append(
            {
                "name": "API aggregate reconciliation",
                "passed": False,
                "detail": "skipped — no aggregate payload available",
            }
        )

    passed_all = all(c["passed"] for c in checks)
    return {
        "status": "PASS" if passed_all else "FAIL",
        "passed": passed_all,
        "checks": checks,
    }
