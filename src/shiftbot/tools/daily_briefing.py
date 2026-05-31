"""Tool: earnings summary for a single day."""

from agents import function_tool
from shared.dates import local_now
from shiftbot.db import get_conn


@function_tool
async def daily_briefing(user_id: str, target_date: str = "") -> str:
    """Return an earnings breakdown for a specific date (default: today).

    USE WHEN: the user asks how much they earned today, for their daily
    summary, or for a breakdown of a specific date.

    Args:
        user_id:     Telegram user ID string.
        target_date: Date in YYYY-MM-DD format. Defaults to today (local timezone).
    """
    if not target_date:
        target_date = local_now().strftime("%Y-%m-%d")

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT platform, gross_pay, tips, hours, km
            FROM shifts
            WHERE user_id = ? AND shift_date = ?
            ORDER BY id ASC
            """,
            (user_id, target_date),
        ).fetchall()

    if not rows:
        return f"No shifts logged for <b>{target_date}</b>."

    total_gross = sum(r["gross_pay"] for r in rows)
    total_tips = sum(r["tips"] for r in rows)
    total_net = total_gross + total_tips
    total_hours = sum(r["hours"] for r in rows)
    total_km = sum(r["km"] for r in rows)
    effective_rate = round(total_net / total_hours, 2) if total_hours > 0 else 0.0

    platform_lines = []
    for row in rows:
        net = row["gross_pay"] + row["tips"]
        platform_lines.append(f"  <b>{row['platform']}</b>: ${net:.2f} ({row['hours']:.1f} h)")

    km_line = f"\n<b>Distance:</b> {total_km:.1f} km" if total_km > 0 else ""

    return (
        f"<b>Daily briefing - {target_date}</b>\n\n"
        + "\n".join(platform_lines)
        + f"\n\n<b>Total net:</b> ${total_net:.2f}\n"
        f"<b>Hours:</b> {total_hours:.1f} h  |  "
        f"<b>Effective rate:</b> ${effective_rate:.2f}/h"
        f"{km_line}"
    )
