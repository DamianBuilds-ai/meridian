"""Tool: list recent shifts for a user."""

from agents import function_tool
from shiftbot.db import get_conn


@function_tool
async def list_shifts(user_id: str, limit: int = 10) -> str:
    """List the most recent logged shifts for a user.

    USE WHEN: the user asks to see their recent shifts, review history,
    or check what has been logged.

    Args:
        user_id: Telegram user ID string.
        limit:   Maximum number of shifts to return (default 10, max 50).
    """
    limit = min(max(1, limit), 50)

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, shift_date, platform, gross_pay, tips, hours, km, notes
            FROM shifts
            WHERE user_id = ?
            ORDER BY shift_date DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    if not rows:
        return "No shifts logged yet. Send your first shift details to get started."

    lines = [f"<b>Last {len(rows)} shift(s):</b>\n"]
    for row in rows:
        net = row["gross_pay"] + row["tips"]
        hourly = round(net / row["hours"], 2) if row["hours"] > 0 else 0.0
        km_str = f"  {row['km']:.0f} km" if row["km"] > 0 else ""
        note_str = f"  - {row['notes']}" if row["notes"] else ""
        lines.append(
            f"<code>#{row['id']}</code> {row['shift_date']}  "
            f"<b>{row['platform']}</b>  "
            f"${net:.2f} ({row['hours']:.1f} h @ ${hourly:.2f}/h)"
            f"{km_str}{note_str}"
        )

    return "\n".join(lines)
