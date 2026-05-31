"""Tool: earnings summary for the trailing 7-day window."""

from agents import function_tool
from shared.dates import local_now
from shiftbot.db import get_conn


@function_tool
async def weekly_summary(user_id: str, week_offset: int = 0) -> str:
    """Return an earnings breakdown for a rolling 7-day window.

    USE WHEN: the user asks for their weekly summary, total earnings
    this week, or a week-over-week comparison.

    Args:
        user_id:     Telegram user ID string.
        week_offset: 0 = current 7 days, 1 = previous 7 days, etc.
                     Use this to compare weeks on request.
    """
    now = local_now()
    # Rolling window: today minus (7*offset) through today minus (7*offset + 6)
    from datetime import timedelta

    end_date = (now - timedelta(days=7 * week_offset)).strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=7 * week_offset + 6)).strftime("%Y-%m-%d")

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT shift_date, platform, gross_pay, tips, hours, km
            FROM shifts
            WHERE user_id = ? AND shift_date BETWEEN ? AND ?
            ORDER BY shift_date ASC
            """,
            (user_id, start_date, end_date),
        ).fetchall()

    if not rows:
        return f"No shifts logged between <b>{start_date}</b> and <b>{end_date}</b>."

    total_gross = sum(r["gross_pay"] for r in rows)
    total_tips = sum(r["tips"] for r in rows)
    total_net = total_gross + total_tips
    total_hours = sum(r["hours"] for r in rows)
    total_km = sum(r["km"] for r in rows)
    effective_rate = round(total_net / total_hours, 2) if total_hours > 0 else 0.0
    shift_count = len(rows)

    # Platform breakdown
    by_platform: dict[str, dict] = {}
    for row in rows:
        p = row["platform"]
        if p not in by_platform:
            by_platform[p] = {"net": 0.0, "hours": 0.0}
        by_platform[p]["net"] += row["gross_pay"] + row["tips"]
        by_platform[p]["hours"] += row["hours"]

    platform_lines = []
    for pname, pdata in sorted(by_platform.items()):
        platform_lines.append(
            f"  <b>{pname}</b>: ${pdata['net']:.2f} ({pdata['hours']:.1f} h)"
        )

    km_line = f"\n<b>Distance:</b> {total_km:.1f} km" if total_km > 0 else ""
    label = "This week" if week_offset == 0 else f"Week -{week_offset}"

    return (
        f"<b>{label} ({start_date} to {end_date})</b>\n"
        f"<b>Shifts worked:</b> {shift_count}\n\n"
        + "\n".join(platform_lines)
        + f"\n\n<b>Total net:</b> ${total_net:.2f}\n"
        f"<b>Hours:</b> {total_hours:.1f} h  |  "
        f"<b>Effective rate:</b> ${effective_rate:.2f}/h"
        f"{km_line}"
    )
