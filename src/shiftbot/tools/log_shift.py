"""Tool: log a single earnings shift for a gig worker."""

from datetime import datetime, timezone

from agents import function_tool
from shared.dates import local_now
from shiftbot.db import get_conn


@function_tool
async def log_shift(
    user_id: str,
    shift_date: str,
    platform: str,
    gross_pay: float,
    hours: float,
    tips: float = 0.0,
    km: float = 0.0,
    notes: str = "",
) -> str:
    """Record one completed earnings shift in the database.

    USE WHEN: the user provides shift details (earnings, hours, date, platform)
    and wants to log them. Call this after receiving structured data - either
    typed by the user or extracted by the upstream OCR step.

    Args:
        user_id:    Telegram user ID (string) - used for multi-user isolation.
        shift_date: Date of the shift in YYYY-MM-DD format.
        platform:   Gig platform label (e.g. "rideshare", "delivery", "freelance").
        gross_pay:  Total earnings before deductions, in the user's currency.
        hours:      Hours worked during the shift.
        tips:       Tips received (default 0).
        km:         Kilometres driven (default 0 if not applicable).
        notes:      Any free-text notes about the shift.
    """
    created_at = local_now().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    net = gross_pay + tips
    hourly = round(net / hours, 2) if hours > 0 else 0.0

    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO shifts
                (user_id, shift_date, platform, gross_pay, tips, hours, km, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, shift_date, platform, gross_pay, tips, hours, km, notes, created_at),
        )
        shift_id = cursor.lastrowid

    km_line = f"\n<b>Distance:</b> {km:.1f} km" if km > 0 else ""
    notes_line = f"\n<b>Notes:</b> {notes}" if notes else ""

    return (
        f"<b>Shift logged</b> (ID {shift_id})\n"
        f"<b>Date:</b> {shift_date}  |  <b>Platform:</b> {platform}\n"
        f"<b>Gross:</b> ${gross_pay:.2f}  <b>Tips:</b> ${tips:.2f}  "
        f"<b>Net:</b> ${net:.2f}\n"
        f"<b>Hours:</b> {hours:.1f} h  |  <b>Effective rate:</b> ${hourly:.2f}/h"
        f"{km_line}{notes_line}"
    )
