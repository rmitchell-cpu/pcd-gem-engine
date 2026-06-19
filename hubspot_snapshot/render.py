"""Render the snapshot into a self-contained, sortable/filterable HTML artifact.

The output is a single ``.html`` file with all CSS and JS inlined (no external
assets, no network calls) so it can be emailed, archived, or opened offline.
The tables are server-rendered (work without JS) and progressively enhanced
with click-to-sort and live filtering.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

from .metrics import RATE_KEYS, RATE_LABELS


# -- formatting helpers ----------------------------------------------------
def _int(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def _pct(frac: Any) -> str:
    try:
        return f"{float(frac) * 100:.2f}%"
    except (TypeError, ValueError):
        return "0.00%"


def _esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _arrow(direction: str) -> str:
    return {"up": "▲", "down": "▼", "flat": "▬"}.get(direction, "▬")


# -- components ------------------------------------------------------------
def _kpi_cards(rollup: dict[str, Any], tr: dict[str, Any]) -> str:
    cards: list[str] = []

    # Volume cards (sent / delivered) with % change vs prior period.
    for key, label in (("sent", "Sent"), ("delivered", "Delivered")):
        vol = tr["volume"][key]
        pct = vol["pct_change"]
        direction = "up" if pct > 0 else ("down" if pct < 0 else "flat")
        cards.append(
            f"""
        <div class="kpi">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{_int(rollup['counters'][key])}</div>
          <div class="kpi-trend {direction}">{_arrow(direction)} {pct:+.1f}% vs prior 30d</div>
        </div>"""
        )

    # Rate cards with delta in percentage points and good/bad sentiment colour.
    for key in RATE_KEYS:
        rt = tr["rates"][key]
        cards.append(
            f"""
        <div class="kpi">
          <div class="kpi-label">{_esc(RATE_LABELS[key])}</div>
          <div class="kpi-value">{_pct(rollup['rates'][key])}</div>
          <div class="kpi-trend {rt['sentiment']}">{_arrow(rt['direction'])} {rt['delta_pp']:+.2f}pp vs prior 30d</div>
        </div>"""
        )

    return '<section class="kpi-grid">' + "".join(cards) + "</section>"


def _verification_banner(verification: dict[str, Any]) -> str:
    status = verification["status"]
    cls = "ok" if verification["passed"] else "fail"
    rows = "".join(
        f'<tr class="{"ok" if c["passed"] else "fail"}">'
        f'<td>{"✓" if c["passed"] else "✗"}</td>'
        f"<td>{_esc(c['name'])}</td><td>{_esc(c['detail'])}</td></tr>"
        for c in verification["checks"]
    )
    return f"""
    <section class="verify {cls}">
      <details {"open" if not verification["passed"] else ""}>
        <summary><span class="badge {cls}">VERIFICATION: {status}</span>
        <span class="muted">numbers reconciled against the HubSpot API — click to expand</span></summary>
        <table class="verify-table">
          <thead><tr><th></th><th>Check</th><th>Detail</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </details>
    </section>"""


def _daily_table(groups: list[dict[str, Any]]) -> str:
    headers = [
        ("Day", "text"),
        ("Emails", "num"),
        ("Sent", "num"),
        ("Delivered", "num"),
        ("Opens", "num"),
        ("Clicks", "num"),
        ("Open %", "num"),
        ("Click %", "num"),
        ("CTOR %", "num"),
        ("Bounce %", "num"),
        ("Unsub %", "num"),
    ]
    head = "".join(
        f'<th data-type="{t}">{_esc(h)}</th>' for h, t in headers
    )
    body_rows = []
    for g in groups:
        c, r = g["counters"], g["rates"]
        body_rows.append(
            "<tr>"
            f'<td data-sort="{_esc(g["day"])}">{_esc(g["day"])}</td>'
            f'<td data-sort="{g["email_count"]}">{_int(g["email_count"])}</td>'
            f'<td data-sort="{c["sent"]}">{_int(c["sent"])}</td>'
            f'<td data-sort="{c["delivered"]}">{_int(c["delivered"])}</td>'
            f'<td data-sort="{c["open"]}">{_int(c["open"])}</td>'
            f'<td data-sort="{c["click"]}">{_int(c["click"])}</td>'
            f'<td data-sort="{r["open_rate"]}">{_pct(r["open_rate"])}</td>'
            f'<td data-sort="{r["click_rate"]}">{_pct(r["click_rate"])}</td>'
            f'<td data-sort="{r["ctor"]}">{_pct(r["ctor"])}</td>'
            f'<td data-sort="{r["bounce_rate"]}">{_pct(r["bounce_rate"])}</td>'
            f'<td data-sort="{r["unsub_rate"]}">{_pct(r["unsub_rate"])}</td>'
            "</tr>"
        )
    return f"""
    <h2>Daily summary</h2>
    <table class="data sortable" id="daily">
      <thead><tr>{head}</tr></thead>
      <tbody>{"".join(body_rows)}</tbody>
    </table>"""


def _detail_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        ("Day", "text"),
        ("Email", "text"),
        ("Subject", "text"),
        ("State", "text"),
        ("Sent", "num"),
        ("Delivered", "num"),
        ("Opens", "num"),
        ("Clicks", "num"),
        ("Bounces", "num"),
        ("Unsubs", "num"),
        ("Open %", "num"),
        ("Click %", "num"),
        ("CTOR %", "num"),
        ("Bounce %", "num"),
        ("Unsub %", "num"),
    ]
    head = "".join(f'<th data-type="{t}">{_esc(h)}</th>' for h, t in headers)

    days = sorted({r["day"] for r in rows if r["day"]}, reverse=True)
    day_opts = "".join(f'<option value="{_esc(d)}">{_esc(d)}</option>' for d in days)

    body_rows = []
    for row in rows:
        c, r = row["counters"], row["rates"]
        body_rows.append(
            f'<tr data-day="{_esc(row["day"])}">'
            f'<td data-sort="{_esc(row["day"])}">{_esc(row["day"])}</td>'
            f'<td data-sort="{_esc(row["name"].lower())}">{_esc(row["name"])}</td>'
            f'<td data-sort="{_esc(row["subject"].lower())}">{_esc(row["subject"])}</td>'
            f'<td data-sort="{_esc(row["state"].lower())}">{_esc(row["state"])}</td>'
            f'<td data-sort="{c["sent"]}">{_int(c["sent"])}</td>'
            f'<td data-sort="{c["delivered"]}">{_int(c["delivered"])}</td>'
            f'<td data-sort="{c["open"]}">{_int(c["open"])}</td>'
            f'<td data-sort="{c["click"]}">{_int(c["click"])}</td>'
            f'<td data-sort="{c["bounce"]}">{_int(c["bounce"])}</td>'
            f'<td data-sort="{c["unsubscribed"]}">{_int(c["unsubscribed"])}</td>'
            f'<td data-sort="{r["open_rate"]}">{_pct(r["open_rate"])}</td>'
            f'<td data-sort="{r["click_rate"]}">{_pct(r["click_rate"])}</td>'
            f'<td data-sort="{r["ctor"]}">{_pct(r["ctor"])}</td>'
            f'<td data-sort="{r["bounce_rate"]}">{_pct(r["bounce_rate"])}</td>'
            f'<td data-sort="{r["unsub_rate"]}">{_pct(r["unsub_rate"])}</td>'
            "</tr>"
        )

    return f"""
    <h2>Per-email detail <span class="muted">({len(rows)} emails)</span></h2>
    <div class="controls">
      <input type="search" id="filter" placeholder="Filter by name, subject, state…">
      <select id="dayFilter"><option value="">All days</option>{day_opts}</select>
      <span class="muted" id="rowCount"></span>
    </div>
    <table class="data sortable filterable" id="detail">
      <thead><tr>{head}</tr></thead>
      <tbody>{"".join(body_rows)}</tbody>
    </table>"""


_CSS = """
:root{--bg:#0f172a;--card:#1e293b;--line:#334155;--fg:#e2e8f0;--muted:#94a3b8;
--good:#34d399;--bad:#f87171;--accent:#38bdf8;--head:#0b1220}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:24px}
header h1{margin:0 0 4px;font-size:22px}
.stamp{color:var(--muted);font-size:13px;margin-bottom:20px}
.stamp b{color:var(--fg)}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi-label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.kpi-value{font-size:26px;font-weight:650;margin:4px 0}
.kpi-trend{font-size:12px}
.kpi-trend.good,.kpi-trend.up{color:var(--good)}
.kpi-trend.bad,.kpi-trend.down{color:var(--bad)}
.kpi-trend.flat,.kpi-trend.neutral{color:var(--muted)}
h2{margin:28px 0 10px;font-size:17px}
.muted{color:var(--muted);font-weight:400;font-size:13px}
.controls{display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.controls input,.controls select{background:var(--card);color:var(--fg);
border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:13px}
.controls input{min-width:280px}
table.data{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px}
table.data th,table.data td{padding:9px 11px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
table.data th:first-child,table.data td:first-child,
table.data th:nth-child(2),table.data td:nth-child(2),
table.data th:nth-child(3),table.data td:nth-child(3),
table.data td:nth-child(4),table.data th:nth-child(4){text-align:left}
table.data thead th{background:var(--head);position:sticky;top:0;color:var(--muted);
font-weight:600;cursor:pointer;user-select:none}
table.sortable thead th:hover{color:var(--accent)}
table.data thead th.sorted-asc::after{content:" ▲";color:var(--accent)}
table.data thead th.sorted-desc::after{content:" ▼";color:var(--accent)}
table.data tbody tr:hover{background:#243043}
.verify{margin:18px 0;border-radius:10px;border:1px solid var(--line);background:var(--card);padding:4px 14px}
.verify summary{cursor:pointer;padding:10px 0;list-style:none}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:700;font-size:12px;margin-right:8px}
.badge.ok{background:rgba(52,211,153,.15);color:var(--good);border:1px solid var(--good)}
.badge.fail{background:rgba(248,113,113,.15);color:var(--bad);border:1px solid var(--bad)}
.verify-table{width:100%;border-collapse:collapse;margin:8px 0 14px;font-size:13px}
.verify-table td,.verify-table th{padding:6px 8px;text-align:left;border-bottom:1px solid var(--line)}
.verify-table tr.ok td:first-child{color:var(--good)}
.verify-table tr.fail td:first-child{color:var(--bad)}
footer{color:var(--muted);font-size:12px;margin-top:30px}
"""

_JS = """
(function(){
  // Click-to-sort for any table.sortable.
  document.querySelectorAll('table.sortable').forEach(function(table){
    var ths = table.tHead.rows[0].cells;
    Array.prototype.forEach.call(ths, function(th, idx){
      th.addEventListener('click', function(){
        var numeric = th.getAttribute('data-type') === 'num';
        var asc = !th.classList.contains('sorted-asc');
        Array.prototype.forEach.call(ths, function(o){o.classList.remove('sorted-asc','sorted-desc');});
        th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
        var rows = Array.prototype.slice.call(table.tBodies[0].rows);
        rows.sort(function(a,b){
          var x=a.cells[idx].getAttribute('data-sort'), y=b.cells[idx].getAttribute('data-sort');
          if(numeric){x=parseFloat(x)||0;y=parseFloat(y)||0;return asc?x-y:y-x;}
          x=(x||'').toString();y=(y||'').toString();
          return asc?x.localeCompare(y):y.localeCompare(x);
        });
        rows.forEach(function(r){table.tBodies[0].appendChild(r);});
      });
    });
  });

  // Live text + day filtering for the detail table.
  var detail=document.getElementById('detail');
  var filter=document.getElementById('filter');
  var dayFilter=document.getElementById('dayFilter');
  var counter=document.getElementById('rowCount');
  function applyFilter(){
    if(!detail) return;
    var q=(filter && filter.value || '').toLowerCase().trim();
    var day=dayFilter && dayFilter.value || '';
    var shown=0, rows=detail.tBodies[0].rows;
    for(var i=0;i<rows.length;i++){
      var r=rows[i];
      var matchDay=!day || r.getAttribute('data-day')===day;
      var matchText=!q || r.textContent.toLowerCase().indexOf(q)>-1;
      var vis=matchDay && matchText;
      r.style.display=vis?'':'none';
      if(vis) shown++;
    }
    if(counter) counter.textContent=shown+' shown';
  }
  if(filter) filter.addEventListener('input', applyFilter);
  if(dayFilter) dayFilter.addEventListener('change', applyFilter);
  applyFilter();
})();
"""


def render_html(snapshot: dict[str, Any]) -> str:
    """Render the full artifact from a snapshot dict (see cli.build_snapshot)."""
    meta = snapshot["meta"]
    generated = meta["generated_at"]
    window = meta["window"]
    prior = meta["prior_window"]

    parts = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>HubSpot Email Daily Snapshot — {_esc(window['start'])} to {_esc(window['end'])}</title>",
        f"<style>{_CSS}</style></head><body><div class=\"wrap\">",
        "<header><h1>HubSpot Marketing Email — Daily Snapshot</h1>",
        f'<div class="stamp">Point-in-time snapshot generated <b>{_esc(generated)}</b> · '
        f"Window <b>{_esc(window['start'])} → {_esc(window['end'])}</b> (last 30 days) · "
        f"Prior period <b>{_esc(prior['start'])} → {_esc(prior['end'])}</b> · "
        f"Portal <b>{_esc(meta.get('portal_id', 'n/a'))}</b></div></header>",
        _verification_banner(snapshot["verification"]),
        _kpi_cards(snapshot["rollup"], snapshot["trend"]),
        _daily_table(snapshot["daily"]),
        _detail_table(snapshot["rows"]),
        '<footer>Rates computed from raw counts: open=opens/delivered, click=clicks/delivered, '
        "CTOR=clicks/opens, bounce=bounces/sent, unsub=unsubs/delivered. "
        "Generated by pcd-gem-engine / hubspot_snapshot. "
        f"Source records: {len(snapshot['rows'])} emails across {len(snapshot['daily'])} send-days.</footer>",
        f"<script>{_JS}</script>",
        "</div></body></html>",
    ]
    return "".join(parts)
