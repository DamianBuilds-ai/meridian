"""
system_health - aggregate status across registered domains from local state files.

Each domain that participates in Lighthouse writes a small JSON file to the
directory given by LIGHTHOUSE_DOMAINS_DIR (default: /app/data/lighthouse/domains/).

Expected file format (one JSON file per domain, e.g. assistant.json):
{
    "domain":    "assistant",           -- display name
    "status":    "ok",                  -- ok | warn | error | unknown
    "message":   "All good.",           -- one-line human summary
    "last_seen": "2026-05-31T09:00:00Z" -- ISO 8601 UTC timestamp (optional)
}

TODO: Replace the stub seed block below with real domain state writers in each
      participating bot. See docs/adding-a-bot.md for the state-file convention.

Snoozed domains (written by snooze_domain tool) are suppressed from the alerts
section until their snooze window expires.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from agents import function_tool
from lighthouse._db import connect


def _domains_dir() -> Path:
    raw = os.environ.get("LIGHTHOUSE_DOMAINS_DIR", "/app/data/lighthouse/domains")
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _active_snoozes() -> set[str]:
    """Return domain names whose snooze window has not yet expired."""
    now = int(time.time())
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT domain FROM snoozes WHERE until_ts > ? "
            "ORDER BY until_ts DESC",
            (now,),
        ).fetchall()
        return {r["domain"] for r in rows}
    finally:
        conn.close()


def _seed_stub_files(d: Path) -> None:
    """Write illustrative stub state files if the directory is empty.

    TODO: Remove this stub once real domain bots write their own state files.
          Each participating bot should write its JSON health file to LIGHTHOUSE_DOMAINS_DIR
          on startup and update it periodically. See docs/adding-a-bot.md.
    """
    if any(d.glob("*.json")):
        return  # real files already present

    stubs = [
        {
            "domain": "assistant",
            "status": "ok",
            "message": "Processed 42 messages today, no errors.",
            "last_seen": "2026-05-31T08:55:00Z",
        },
        {
            "domain": "weather",
            "status": "warn",
            "message": "Weather API returned HTTP 429 twice in the last hour. Retrying.",
            "last_seen": "2026-05-31T08:40:00Z",
        },
        {
            "domain": "notes",
            "status": "ok",
            "message": "12 notes saved this week, database healthy.",
            "last_seen": "2026-05-31T07:30:00Z",
        },
    ]
    for stub in stubs:
        (d / f"{stub['domain']}.json").write_text(json.dumps(stub, indent=2))


STATUS_ICON = {
    "ok": "green_circle",
    "warn": "yellow_circle",
    "error": "red_circle",
    "unknown": "white_circle",
}

TELEGRAM_ICON = {
    "ok": "✅",       # checkmark
    "warn": "⚠️",  # warning - stripped by sanitize; plain text fallback below
    "error": "❌",    # red X
    "unknown": "⭕",  # hollow circle
}

STATUS_TEXT = {
    "ok": "OK",
    "warn": "WARN",
    "error": "ERROR",
    "unknown": "?",
}


@function_tool
async def system_health(include_snoozed: bool = False) -> str:
    """Return an aggregated health snapshot across all registered automation domains.

    USE WHEN: The user asks "how is everything?", "what's the status?", "any issues?",
    "health check", "stack status", or similar broad system-state questions.

    Args:
        include_snoozed: If True, show snoozed domains in full. Default False (suppressed
                         from alert section but still counted in summary).
    """
    d = _domains_dir()
    _seed_stub_files(d)

    snoozed = _active_snoozes()
    files = sorted(d.glob("*.json"))

    if not files:
        return (
            "<b>System Health</b>\n\n"
            "No domain state files found.\n"
            "Domains must write a JSON status file to <code>LIGHTHOUSE_DOMAINS_DIR</code> "
            "to appear here.\n"
            "See <code>docs/adding-a-bot.md</code> for the state-file convention."
        )

    results: list[dict] = []
    parse_errors: list[str] = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            results.append(data)
        except (json.JSONDecodeError, OSError) as exc:
            parse_errors.append(f"{f.name}: {exc}")

    total = len(results)
    counts = {"ok": 0, "warn": 0, "error": 0, "unknown": 0}
    for r in results:
        s = r.get("status", "unknown")
        counts[s if s in counts else "unknown"] += 1

    lines: list[str] = ["<b>System Health</b>"]
    lines.append(
        f"<code>{total} domain(s)</code>  "
        f"OK:{counts['ok']}  WARN:{counts['warn']}  ERROR:{counts['error']}"
    )
    lines.append("")

    for r in results:
        name = r.get("domain", "unknown")
        status = r.get("status", "unknown")
        message = r.get("message", "")
        last_seen = r.get("last_seen", "")
        is_snoozed = name in snoozed

        icon = STATUS_TEXT[status if status in STATUS_TEXT else "unknown"]
        snooze_tag = " [snoozed]" if is_snoozed else ""

        if is_snoozed and not include_snoozed and status not in ("error",):
            # Show a one-liner for snoozed non-error domains
            lines.append(f"<i>{name}</i>: snoozed, last status {icon}")
            continue

        lines.append(f"<b>{name}</b> [{icon}]{snooze_tag}")
        if message:
            lines.append(f"  {message}")
        if last_seen:
            lines.append(f"  Last seen: <code>{last_seen}</code>")

    if parse_errors:
        lines.append("")
        lines.append("<b>Parse errors</b>")
        for e in parse_errors:
            lines.append(f"  {e}")

    return "\n".join(lines)
