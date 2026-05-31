"""
snooze_domain - temporarily suppress a domain from health alerts.

Writes a snooze record to SQLite. system_health reads active snoozes and
suppresses non-error alerts for snoozed domains until the window expires.
Snooze windows are soft: errors still surface even on snoozed domains.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from agents import function_tool
from lighthouse._db import connect


@function_tool
async def snooze_domain(
    domain: str,
    duration_minutes: int = 60,
    reason: str = "",
) -> str:
    """Snooze health alerts for a specific domain for a set number of minutes.

    USE WHEN: The user says "snooze weather", "ignore X for an hour", "mute Y alerts",
    "suppress notifications for Z while we fix it", or similar alert-suppression requests.
    Errors (status=error) will still surface even during a snooze.

    Args:
        domain:            The domain name to snooze (must match the domain field in its state file).
        duration_minutes:  How long to snooze in minutes. Default 60, max 1440 (24h).
        reason:            Optional explanation (e.g. "known flap, fix in progress").
    """
    domain = (domain or "").strip()
    if not domain:
        return "<b>Snooze Domain</b>\n\nDomain name is required."

    duration_minutes = min(max(1, duration_minutes), 1440)
    now = int(time.time())
    until_ts = now + (duration_minutes * 60)
    until_str = datetime.fromtimestamp(until_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    conn = connect()
    try:
        conn.execute(
            "INSERT INTO snoozes (domain, until_ts, reason, created_at) "
            "VALUES (?, ?, ?, ?)",
            (domain, until_ts, (reason or "").strip() or None, now),
        )
        # Count active snoozes for this domain
        active = conn.execute(
            "SELECT COUNT(*) FROM snoozes WHERE domain = ? AND until_ts > ?",
            (domain, now),
        ).fetchone()[0]
    finally:
        conn.close()

    reason_line = f"\n  reason: {reason}" if reason else ""
    return (
        f"<b>Snoozed</b> <code>{domain}</code>\n"
        f"  until: {until_str} ({duration_minutes} min){reason_line}\n"
        f"  active snooze windows for this domain: {active}\n\n"
        f"<i>Note: error-level alerts still surface during a snooze.</i>"
    )
