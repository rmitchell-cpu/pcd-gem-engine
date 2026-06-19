"""Pure metric computations for the marketing-email snapshot.

Everything here is deterministic and free of network/IO so it can be unit
tested against fixtures. The HubSpot client (:mod:`hubspot_snapshot.client`)
normalises raw API payloads into the ``EmailRecord`` shape consumed here.

Rate definitions (all returned as fractions in [0, 1]); each is computed from
the *raw counters* rather than trusting any precomputed API ratio, so the
numbers in the artifact can be audited from the counts shown next to them:

    open rate    = unique opens   / delivered
    click rate   = unique clicks  / delivered
    CTOR         = unique clicks  / unique opens   (click-to-open rate)
    bounce rate  = bounces        / sent
    unsub rate   = unsubscribes   / delivered

``delivered`` falls back to ``sent - bounces`` when the API omits a delivered
counter.
"""

from __future__ import annotations

from typing import Any

# Canonical counter keys carried through the pipeline.
COUNTER_KEYS = (
    "sent",
    "delivered",
    "open",
    "click",
    "bounce",
    "unsubscribed",
)

# The five headline rates plus their human labels and the formula they use.
RATE_KEYS = ("open_rate", "click_rate", "ctor", "bounce_rate", "unsub_rate")

RATE_LABELS = {
    "open_rate": "Open rate",
    "click_rate": "Click rate",
    "ctor": "CTOR",
    "bounce_rate": "Bounce rate",
    "unsub_rate": "Unsub rate",
}

# Rates where a higher number is the better outcome. Used for trend colouring.
HIGHER_IS_BETTER = {
    "open_rate": True,
    "click_rate": True,
    "ctor": True,
    "bounce_rate": False,
    "unsub_rate": False,
}


def _safe_div(numerator: float, denominator: float) -> float:
    """Divide, returning 0.0 when the denominator is zero/missing."""
    return numerator / denominator if denominator else 0.0


def normalize_counters(counters: dict[str, Any]) -> dict[str, int]:
    """Coerce a raw counters dict to the canonical integer counter set.

    ``delivered`` is derived from ``sent - bounce`` when absent.
    """
    out: dict[str, int] = {}
    for key in COUNTER_KEYS:
        try:
            out[key] = int(counters.get(key, 0) or 0)
        except (TypeError, ValueError):
            out[key] = 0
    if not counters.get("delivered"):
        out["delivered"] = max(out["sent"] - out["bounce"], 0)
    return out


def compute_rates(counters: dict[str, Any]) -> dict[str, float]:
    """Compute the five headline rates from a counters dict."""
    c = normalize_counters(counters)
    return {
        "open_rate": _safe_div(c["open"], c["delivered"]),
        "click_rate": _safe_div(c["click"], c["delivered"]),
        "ctor": _safe_div(c["click"], c["open"]),
        "bounce_rate": _safe_div(c["bounce"], c["sent"]),
        "unsub_rate": _safe_div(c["unsubscribed"], c["delivered"]),
    }


def sum_counters(records: list[dict[str, Any]]) -> dict[str, int]:
    """Sum the canonical counters across a list of records/rows."""
    total = {key: 0 for key in COUNTER_KEYS}
    for rec in records:
        c = normalize_counters(rec.get("counters", rec))
        for key in COUNTER_KEYS:
            total[key] += c[key]
    return total


def email_row(record: dict[str, Any]) -> dict[str, Any]:
    """Build a per-email row: metadata + raw counters + computed rates."""
    counters = normalize_counters(record.get("counters", {}))
    return {
        "id": str(record.get("id", "")),
        "name": record.get("name") or "(untitled)",
        "subject": record.get("subject") or "",
        "state": record.get("state") or "",
        "type": record.get("type") or "",
        "day": record.get("send_date") or "",
        "send_ts": record.get("send_ts") or 0,
        "counters": counters,
        "rates": compute_rates(counters),
    }


def daily_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group per-email rows by send day, descending by date.

    Each group carries the email count, summed counters, and rates recomputed
    from those summed counters.
    """
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_day.setdefault(row["day"], []).append(row)

    groups = []
    for day in sorted(by_day, reverse=True):
        members = by_day[day]
        counters = sum_counters(members)
        groups.append(
            {
                "day": day,
                "email_count": len(members),
                "counters": counters,
                "rates": compute_rates(counters),
            }
        )
    return groups


def rollup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate all rows into a single rollup (counters + rates + email count)."""
    counters = sum_counters(rows)
    return {
        "email_count": len(rows),
        "counters": counters,
        "rates": compute_rates(counters),
    }


def trend(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    """Compare a current rollup to a prior-period rollup.

    Returns, per rate, the current/prior fractions, the delta in percentage
    *points*, and a ``direction`` of "up"/"down"/"flat" classified as
    good/bad/neutral via :data:`HIGHER_IS_BETTER`. Also returns the volume
    deltas for sent/delivered as percentage change.
    """
    cur_rates = current.get("rates", {})
    pri_rates = prior.get("rates", {})
    rate_trends: dict[str, Any] = {}
    for key in RATE_KEYS:
        cur = cur_rates.get(key, 0.0)
        pri = pri_rates.get(key, 0.0)
        delta_pp = (cur - pri) * 100.0
        if abs(delta_pp) < 1e-9:
            direction, sentiment = "flat", "neutral"
        else:
            direction = "up" if delta_pp > 0 else "down"
            improving = (delta_pp > 0) == HIGHER_IS_BETTER[key]
            sentiment = "good" if improving else "bad"
        rate_trends[key] = {
            "current": cur,
            "prior": pri,
            "delta_pp": delta_pp,
            "direction": direction,
            "sentiment": sentiment,
        }

    cur_c = current.get("counters", {})
    pri_c = prior.get("counters", {})
    volume_trends: dict[str, Any] = {}
    for key in ("sent", "delivered"):
        cur = cur_c.get(key, 0)
        pri = pri_c.get(key, 0)
        pct = _safe_div((cur - pri) * 100.0, pri) if pri else (100.0 if cur else 0.0)
        volume_trends[key] = {"current": cur, "prior": pri, "pct_change": pct}

    return {
        "rates": rate_trends,
        "volume": volume_trends,
        "email_count": {
            "current": current.get("email_count", 0),
            "prior": prior.get("email_count", 0),
        },
    }
