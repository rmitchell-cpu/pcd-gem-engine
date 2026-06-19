"""Offline tests for the HubSpot marketing-email snapshot generator.

These exercise the full transform/verify/render pipeline against a fixture so
the math (rates, daily grouping, rollup, trend) and the API-reconciliation
logic can be validated without network access to api.hubapi.com.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hubspot_snapshot.cli import build_snapshot, run_fixture
from hubspot_snapshot.client import extract_counters, normalize_email, parse_publish_ts
from hubspot_snapshot.metrics import compute_rates, daily_groups, email_row, rollup, trend
from hubspot_snapshot.render import render_html

FIXTURE = Path(__file__).parent / "fixtures" / "hubspot_sample.json"
NOW = datetime(2026, 6, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def snapshot():
    class Args:
        fixture = str(FIXTURE)
        days = 30

    return run_fixture(Args(), NOW)


# -- rate math -------------------------------------------------------------
def test_compute_rates_basic():
    rates = compute_rates(
        {"sent": 1000, "delivered": 950, "open": 380, "click": 95, "bounce": 50, "unsubscribed": 5}
    )
    assert rates["open_rate"] == pytest.approx(380 / 950)
    assert rates["click_rate"] == pytest.approx(95 / 950)
    assert rates["ctor"] == pytest.approx(95 / 380)
    assert rates["bounce_rate"] == pytest.approx(50 / 1000)
    assert rates["unsub_rate"] == pytest.approx(5 / 950)


def test_compute_rates_zero_denominator():
    rates = compute_rates({"sent": 0, "delivered": 0, "open": 0, "click": 0})
    assert all(v == 0.0 for v in rates.values())


def test_delivered_derived_when_missing():
    c = extract_counters({"counters": {"sent": 100, "bounce": 10}})
    # metrics.normalize_counters fills delivered = sent - bounce
    assert compute_rates(c)["bounce_rate"] == pytest.approx(0.1)
    row = email_row({"counters": c})
    assert row["counters"]["delivered"] == 90


# -- grouping & rollup -----------------------------------------------------
def test_daily_grouping(snapshot):
    days = {g["day"]: g for g in snapshot["daily"]}
    assert set(days) == {"2026-06-18", "2026-06-17"}
    # 2026-06-18 has emails 101 + 102 summed.
    g18 = days["2026-06-18"]
    assert g18["email_count"] == 2
    assert g18["counters"]["sent"] == 3000
    assert g18["counters"]["open"] == 1140
    # groups are sorted descending by day
    assert [g["day"] for g in snapshot["daily"]] == ["2026-06-18", "2026-06-17"]


def test_rollup_totals(snapshot):
    c = snapshot["rollup"]["counters"]
    assert c == {
        "sent": 3500,
        "delivered": 3330,
        "open": 1260,
        "click": 309,
        "bounce": 170,
        "unsubscribed": 17,
    }
    assert snapshot["rollup"]["email_count"] == 3
    assert snapshot["rollup"]["rates"]["open_rate"] == pytest.approx(1260 / 3330)


def test_daily_sums_match_rollup(snapshot):
    total = {k: 0 for k in ("sent", "delivered", "open", "click", "bounce", "unsubscribed")}
    for g in snapshot["daily"]:
        for k in total:
            total[k] += g["counters"][k]
    assert total == snapshot["rollup"]["counters"]


# -- trend -----------------------------------------------------------------
def test_trend_vs_prior(snapshot):
    tr = snapshot["trend"]
    open_t = tr["rates"]["open_rate"]
    assert open_t["current"] == pytest.approx(1260 / 3330)
    assert open_t["prior"] == pytest.approx(300 / 960)
    assert open_t["delta_pp"] == pytest.approx((1260 / 3330 - 300 / 960) * 100)
    assert open_t["direction"] == "up"
    assert open_t["sentiment"] == "good"
    # bounce went 4.00% -> 4.86%, up == bad
    assert tr["rates"]["bounce_rate"]["sentiment"] == "bad"
    assert tr["volume"]["sent"]["pct_change"] == pytest.approx((3500 - 1000) / 1000 * 100)


# -- verification ----------------------------------------------------------
def test_verification_passes(snapshot):
    v = snapshot["verification"]
    assert v["status"] == "PASS"
    assert v["passed"] is True
    assert any("vs API aggregate" in c["name"] for c in v["checks"])
    assert any("vs API ratio" in c["name"] for c in v["checks"])
    assert all(c["passed"] for c in v["checks"])


def test_verification_detects_mismatch():
    from hubspot_snapshot.verify import verify_against_api

    rows = [email_row({"id": "1", "send_date": "2026-06-18",
                        "counters": {"sent": 100, "delivered": 95, "open": 40,
                                     "click": 10, "bounce": 5, "unsubscribed": 1}})]
    bad_aggregate = {"aggregate": {"statistics": {"counters": {
        "sent": 50, "delivered": 48, "open": 5, "click": 1, "bounce": 1, "unsubscribed": 0}}}}
    v = verify_against_api(rows, bad_aggregate)
    # rollup (100) exceeds the API aggregate (50) -> reconciliation fails
    assert v["passed"] is False


def test_verification_no_aggregate():
    from hubspot_snapshot.verify import verify_against_api

    rows = [email_row({"id": "1", "send_date": "2026-06-18", "counters": {"sent": 10}})]
    v = verify_against_api(rows, None)
    assert v["passed"] is False


# -- parsing ---------------------------------------------------------------
def test_parse_publish_ts_iso_and_epoch():
    iso = parse_publish_ts({"publishDate": "2026-06-18T14:00:00Z"})
    assert datetime.fromtimestamp(iso / 1000, tz=timezone.utc).strftime("%Y-%m-%d") == "2026-06-18"
    assert parse_publish_ts({"publishDate": 1750255200000}) == 1750255200000
    assert parse_publish_ts({"publishDate": 1750255200}) == 1750255200000
    assert parse_publish_ts({"name": "no date"}) is None


def test_normalize_email_shape():
    rec = normalize_email(
        {"id": 7, "name": "X", "subject": "Y", "state": "PUBLISHED", "publishDate": "2026-06-18T00:00:00Z"},
        {"statistics": {"counters": {"sent": 10, "open": 5}}},
    )
    assert rec["id"] == "7"
    assert rec["send_date"] == "2026-06-18"
    assert rec["counters"]["sent"] == 10


# -- rendering -------------------------------------------------------------
def test_render_html_self_contained(snapshot):
    out = render_html(snapshot)
    assert out.startswith("<!doctype html>")
    assert "VERIFICATION: PASS" in out
    # no external resource references — fully offline artifact
    assert "http://" not in out and "https://" not in out
    assert "src=" not in out and "<link" not in out
    # KPI + tables present
    assert "Daily summary" in out
    assert "Per-email detail" in out
    assert "Weekly Digest #42" in out
    # point-in-time stamp present
    assert "2026-06-19 12:00:00 UTC" in out
    assert "Open rate" in out


def test_build_snapshot_pure():
    data = json.loads(FIXTURE.read_text())
    cur = [normalize_email(e["email"], e["statistics"]) for e in data["current"]]
    pri = [normalize_email(e["email"], e["statistics"]) for e in data["prior"]]
    snap = build_snapshot(cur, pri, data["aggregate"], {
        "generated_at": "x", "portal_id": "p",
        "window": {"start": "a", "end": "b"},
        "prior_window": {"start": "c", "end": "d"},
    })
    assert snap["rollup"]["email_count"] == 3
    assert snap["verification"]["passed"] is True
