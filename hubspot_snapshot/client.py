"""Thin HubSpot Marketing Email API client (stdlib only).

Uses ``HUBSPOT_TOKEN`` (private-app / OAuth bearer token) and talks to the v3
Marketing Email endpoints:

  * ``GET /marketing/v3/emails``                       — list marketing emails
  * ``GET /marketing/v3/emails/{id}/statistics``       — per-email statistics
  * ``GET /marketing/v3/emails/statistics/list``       — aggregate statistics

Required token scope: ``marketing-email`` (read). No third-party packages — the
deployment environment may not have ``requests`` available, and this keeps the
artifact generator dependency-free.

Network egress note: ``api.hubapi.com`` must be reachable. In restricted
sandboxes it may be blocked ("Host not in allowlist"); add it to the
environment's network egress allowlist.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

BASE_URL = "https://api.hubapi.com"
USER_AGENT = "pcd-gem-engine/hubspot-snapshot"

# States that represent an email that was actually sent to a list.
SENT_STATES = {"PUBLISHED", "SENT", "PUBLISHED_OR_SCHEDULED", "AUTOMATED"}


class HubSpotError(RuntimeError):
    """Raised when the HubSpot API returns a non-retryable error."""


class HubSpotClient:
    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = BASE_URL,
        max_retries: int = 4,
        timeout: int = 30,
    ) -> None:
        self.token = token or os.environ.get("HUBSPOT_TOKEN", "")
        if not self.token:
            raise HubSpotError(
                "HUBSPOT_TOKEN is not set. Export a HubSpot private-app token "
                "with the 'marketing-email' read scope."
            )
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.timeout = timeout

    # -- low-level ---------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        if params:
            # Drop None values; lists are joined with commas (HubSpot convention).
            clean: dict[str, str] = {}
            for key, value in params.items():
                if value is None:
                    continue
                if isinstance(value, (list, tuple)):
                    clean[key] = ",".join(str(v) for v in value)
                else:
                    clean[key] = str(value)
            url += "?" + urllib.parse.urlencode(clean)

        backoff = 2.0
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:500]
                # Retry transient server/rate-limit errors; fail fast otherwise.
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    last_err = HubSpotError(f"HTTP {exc.code}: {body}")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise HubSpotError(f"HTTP {exc.code} for {path}: {body}") from exc
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise HubSpotError(f"Network error for {path}: {exc}") from exc
        raise HubSpotError(f"Exhausted retries for {path}: {last_err}")

    # -- emails ------------------------------------------------------------
    def list_emails(self) -> list[dict[str, Any]]:
        """Page through every marketing email (metadata only)."""
        results: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            page = self._get(
                "/marketing/v3/emails",
                {"limit": 100, "after": after, "archived": "false"},
            )
            results.extend(page.get("results", []))
            after = (page.get("paging", {}).get("next", {}) or {}).get("after")
            if not after:
                break
        return results

    def email_statistics(
        self, email_id: str, start_ms: int, end_ms: int
    ) -> dict[str, Any]:
        """Per-email statistics within the window."""
        return self._get(
            f"/marketing/v3/emails/{email_id}/statistics",
            {"startTimestamp": start_ms, "endTimestamp": end_ms},
        )

    def aggregate_statistics(
        self, start_ms: int, end_ms: int, email_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """Account-wide aggregate statistics for the window (used to verify)."""
        return self._get(
            "/marketing/v3/emails/statistics/list",
            {
                "startTimestamp": start_ms,
                "endTimestamp": end_ms,
                "emailIds": email_ids or None,
            },
        )


# -- normalisation helpers ------------------------------------------------
def _first(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``keys``."""
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


def parse_publish_ts(email: dict[str, Any]) -> int | None:
    """Best-effort extraction of an email's send/publish time in epoch ms."""
    raw = _first(
        email,
        "publishDate",
        "publishedAt",
        "published_at",
        "publish_date",
        "created",
        "createdAt",
    )
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        # Heuristic: seconds vs milliseconds.
        return int(raw if raw > 1e12 else raw * 1000)
    text = str(raw).strip()
    if text.isdigit():
        val = int(text)
        return val if val > 1e12 else val * 1000
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def extract_counters(stats: dict[str, Any]) -> dict[str, Any]:
    """Pull a counters dict out of a HubSpot statistics payload.

    Handles both ``{statistics: {counters: {...}}}`` and a bare counters dict,
    and maps HubSpot's counter key spellings onto our canonical keys.
    """
    node = stats
    # Unwrap optional {"aggregate": {...}} and {"statistics": {...}} wrappers.
    if isinstance(node, dict) and isinstance(node.get("aggregate"), dict):
        node = node["aggregate"]
    if isinstance(node, dict) and isinstance(node.get("statistics"), dict):
        node = node["statistics"]
    counters = node.get("counters", node) if isinstance(node, dict) else {}

    def g(*keys: str) -> int:
        val = _first(counters, *keys, default=0)
        try:
            return int(val or 0)
        except (TypeError, ValueError):
            return 0

    return {
        "sent": g("sent"),
        "delivered": g("delivered"),
        "open": g("open", "uniqueopen", "opens"),
        "click": g("click", "clicks", "uniqueclick"),
        "bounce": g("bounce", "bounces", "hardbounces"),
        "unsubscribed": g("unsubscribed", "unsubscribe", "unsubscribes"),
    }


def normalize_email(email: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    """Combine an email's metadata + statistics into an ``EmailRecord``."""
    ts = parse_publish_ts(email)
    day = (
        datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if ts
        else ""
    )
    return {
        "id": str(_first(email, "id", default="")),
        "name": _first(email, "name", default="(untitled)"),
        "subject": _first(email, "subject", default="")
        or (email.get("content", {}) or {}).get("subject", ""),
        "state": _first(email, "state", default=""),
        "type": _first(email, "type", default=""),
        "send_ts": ts or 0,
        "send_date": day,
        "counters": extract_counters(stats),
    }
