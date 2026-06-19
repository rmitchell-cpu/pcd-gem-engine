# HubSpot Marketing Email — Daily Snapshot Artifact

Generates a self-contained, point-in-time HTML report of marketing-email
performance for the last 30 days, pulled from the HubSpot Marketing Email API.

## What it produces

A single `.html` file (no external assets, opens offline) containing:

- **Rollup KPI header** — Sent, Delivered, Open rate, Click rate, CTOR, Bounce
  rate, Unsub rate, each with a **trend vs. the prior 30-day period**
  (Δ percentage-points for rates, % change for volume; coloured good/bad).
- **Daily summary table** — sends grouped by day, with summed counts and rates
  recomputed from those sums. Sortable.
- **Per-email detail table** — one row per email with raw counts
  (sent / delivered / opens / clicks / bounces / unsubs) **and** computed rates
  (open / click / CTOR / bounce / unsub). Sortable by any column, live text
  filter, and a per-day dropdown filter.
- **Verification panel** — the rolled-up numbers reconciled against the HubSpot
  API aggregate (see below), with a PASS/FAIL badge.
- **Point-in-time stamp** — generation timestamp (UTC) and the exact window /
  prior-window date ranges.

## Rate definitions

All rates are computed from the **raw counts** (never from a precomputed API
ratio), so every percentage in the artifact is auditable against the counts
shown beside it:

| Rate | Formula |
|------|---------|
| Open rate   | unique opens / delivered |
| Click rate  | unique clicks / delivered |
| CTOR        | unique clicks / unique opens |
| Bounce rate | bounces / sent |
| Unsub rate  | unsubscribes / delivered |

`delivered` falls back to `sent − bounces` when the API omits it.

## Usage

```bash
export HUBSPOT_TOKEN=...   # private-app token with 'marketing-email' read scope

# Live pull, last 30 days -> artifacts/hubspot_email_snapshot_<ts>.html
python -m hubspot_snapshot

# Options
python -m hubspot_snapshot --days 30 --out report.html --strict
python -m hubspot_snapshot --dump raw/        # also save the raw API JSON
python -m hubspot_snapshot --fixture tests/fixtures/hubspot_sample.json  # offline
```

`--strict` makes the process exit non-zero when verification fails, so it can
gate a scheduled job or CI step.

## Verification

Before finishing, the generator reconciles its numbers against the API:

1. **Internal consistency** — per-day group counters must sum to the flat
   per-email rollup.
2. **API reconciliation** — summed counters are compared against the aggregate
   from `GET /marketing/v3/emails/statistics/list` for the same window, and the
   recomputed rates are checked against HubSpot's own ratios within 0.5pp
   (scale-agnostic: handles both fraction and percentage conventions).

The result is rendered into the artifact and printed to the console.

## Network requirement

The HubSpot REST host **`api.hubapi.com`** must be reachable. In restricted
sandboxes it may be blocked with `Host not in allowlist: api.hubapi.com` — add
it to the environment's network egress allowlist. (The HubSpot MCP server does
not expose per-email send statistics, so the REST API is required for this.)

## Layout

```
hubspot_snapshot/
  client.py    HubSpot API client (stdlib only) + payload normalisation
  metrics.py   pure rate/grouping/rollup/trend math (unit tested)
  verify.py    reconciliation against the API aggregate
  render.py    self-contained sortable/filterable HTML
  cli.py       pull -> transform -> render -> verify
  example_snapshot.html   demo rendered from the test fixture
```

Tests: `tests/test_hubspot_snapshot.py` (offline, fixture-driven).
