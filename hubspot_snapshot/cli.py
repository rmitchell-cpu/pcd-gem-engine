"""CLI: pull → transform → render → verify the marketing-email snapshot.

Usage:
    python -m hubspot_snapshot                 # live pull, last 30 days
    python -m hubspot_snapshot --days 30       # explicit window length
    python -m hubspot_snapshot --out report.html
    python -m hubspot_snapshot --fixture tests/fixtures/hubspot_sample.json
    python -m hubspot_snapshot --dump raw/     # also save raw API JSON

Exit code is non-zero when verification fails, so it is safe to wire into a
scheduled job / CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .client import HubSpotClient, normalize_email
from .metrics import daily_groups, email_row, rollup, trend
from .render import render_html
from .verify import verify_against_api


def _windows(days: int, now: datetime) -> tuple[int, int, int, int]:
    """Return (cur_start_ms, cur_end_ms, prior_start_ms, prior_end_ms)."""
    end = now
    start = end - timedelta(days=days)
    prior_start = start - timedelta(days=days)
    to_ms = lambda d: int(d.timestamp() * 1000)
    return to_ms(start), to_ms(end), to_ms(prior_start), to_ms(start)


def build_snapshot(
    current_records: list[dict[str, Any]],
    prior_records: list[dict[str, Any]],
    api_aggregate: dict[str, Any] | None,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the full snapshot dict from normalised records (pure / testable)."""
    rows = sorted(
        (email_row(r) for r in current_records),
        key=lambda x: (x["day"], x["counters"]["sent"]),
        reverse=True,
    )
    prior_rows = [email_row(r) for r in prior_records]
    cur_rollup = rollup(rows)
    pri_rollup = rollup(prior_rows)
    return {
        "meta": meta,
        "rows": rows,
        "daily": daily_groups(rows),
        "rollup": cur_rollup,
        "prior_rollup": pri_rollup,
        "trend": trend(cur_rollup, pri_rollup),
        "verification": verify_against_api(rows, api_aggregate),
    }


def _in_window(ts_ms: int, start_ms: int, end_ms: int) -> bool:
    return ts_ms and start_ms <= ts_ms < end_ms


def _fetch_records(
    client: HubSpotClient,
    emails: list[dict[str, Any]],
    start_ms: int,
    end_ms: int,
    dump: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fetch per-email statistics for emails sent within [start_ms, end_ms)."""
    from .client import parse_publish_ts

    records = []
    for email in emails:
        ts = parse_publish_ts(email)
        if not _in_window(ts or 0, start_ms, end_ms):
            continue
        stats = client.email_statistics(str(email["id"]), start_ms, end_ms)
        if dump is not None:
            dump.setdefault("statistics", {})[str(email["id"])] = stats
        records.append(normalize_email(email, stats))
    return records


def run_live(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    client = HubSpotClient()
    cs, ce, ps, pe = _windows(args.days, now)

    dump: dict[str, Any] | None = {} if args.dump else None
    emails = client.list_emails()
    if dump is not None:
        dump["emails"] = emails

    current_records = _fetch_records(client, emails, cs, ce, dump)
    prior_records = _fetch_records(client, emails, ps, pe, dump)

    api_aggregate = client.aggregate_statistics(
        cs, ce, [r["id"] for r in current_records] or None
    )
    if dump is not None:
        dump["aggregate"] = api_aggregate

    meta = _meta(now, cs, ce, ps, pe, _portal_id(client))
    snapshot = build_snapshot(current_records, prior_records, api_aggregate, meta)

    if dump is not None:
        out = Path(args.dump)
        out.mkdir(parents=True, exist_ok=True)
        (out / "raw_api_dump.json").write_text(json.dumps(dump, indent=2, default=str))
    return snapshot


def run_fixture(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    """Build a snapshot from a saved fixture (offline / testing)."""
    data = json.loads(Path(args.fixture).read_text())
    cur = [normalize_email(e["email"], e["statistics"]) for e in data["current"]]
    pri = [normalize_email(e["email"], e["statistics"]) for e in data.get("prior", [])]
    cs, ce, ps, pe = _windows(args.days, now)
    meta = _meta(now, cs, ce, ps, pe, data.get("portal_id", "fixture"))
    return build_snapshot(cur, pri, data.get("aggregate"), meta)


def _portal_id(client: HubSpotClient) -> str:
    try:
        info = client._get("/account-info/v3/details")  # noqa: SLF001 - intentional
        return str(info.get("portalId", "n/a"))
    except Exception:
        return "n/a"


def _meta(
    now: datetime, cs: int, ce: int, ps: int, pe: int, portal_id: str
) -> dict[str, Any]:
    iso = lambda ms: datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "portal_id": portal_id,
        "window": {"start": iso(cs), "end": iso(ce)},
        "prior_window": {"start": iso(ps), "end": iso(pe)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30, help="window length (default 30)")
    parser.add_argument("--out", help="output HTML path (default: artifacts/…)")
    parser.add_argument("--fixture", help="build from a saved JSON fixture (offline)")
    parser.add_argument("--dump", help="directory to also save raw API JSON")
    parser.add_argument(
        "--strict", action="store_true", help="exit non-zero if verification fails"
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    try:
        snapshot = run_fixture(args, now) if args.fixture else run_live(args, now)
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the CLI
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    out_path = (
        Path(args.out)
        if args.out
        else Path("artifacts")
        / f"hubspot_email_snapshot_{now.strftime('%Y%m%dT%H%M%SZ')}.html"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(snapshot), encoding="utf-8")

    v = snapshot["verification"]
    print(f"Artifact written: {out_path}")
    print(f"Emails: {snapshot['rollup']['email_count']} across {len(snapshot['daily'])} days")
    print(f"Verification: {v['status']}")
    for c in v["checks"]:
        print(f"  [{'✓' if c['passed'] else '✗'}] {c['name']}: {c['detail']}")

    if args.strict and not v["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
