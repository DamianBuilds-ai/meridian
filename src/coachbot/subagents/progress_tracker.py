"""
Sub-agent: progress_tracker
Queries session history and computes streaks / totals from the SQLite store.
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta

from agents import Agent, ModelSettings, function_tool
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body
from shared.telegram_format import sanitize_for_telegram

_DB_PATH = os.getenv("COACHBOT_DB_PATH", "./coachbot.db")

SYSTEM_PROMPT = """You are Progress Tracker, a specialist sub-agent for the CoachBot activity tracker.

Your ONLY job is to retrieve and summarise progress data using the available tools.

Telegram HTML ONLY: <b>bold</b>, <i>italic</i>, <code>mono</code>.
BANNED: **bold** *italic* `code` # headers.

Rules:
- Always call a tool first; never answer from memory.
- Present results in a clear, readable format using Telegram HTML.
- If no sessions exist yet, tell the user there is no history yet and encourage them to log a session.
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            activity    TEXT    NOT NULL,
            duration_min INTEGER NOT NULL DEFAULT 0,
            notes       TEXT    NOT NULL DEFAULT '',
            logged_at   TEXT    NOT NULL
        )
    """)
    conn.commit()


@function_tool
async def get_recent_sessions(activity: str = "", limit: int = 10) -> str:
    """Retrieve the most recent logged sessions, optionally filtered by activity.

    USE WHEN: the user asks what they have been practising, their recent sessions,
    or their history for a specific activity.

    Args:
        activity: Filter to a specific activity name. Empty string returns all activities.
        limit:    Maximum number of sessions to return (default 10).
    """
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        if activity:
            rows = conn.execute(
                "SELECT id, activity, duration_min, notes, logged_at "
                "FROM sessions WHERE activity LIKE ? ORDER BY logged_at DESC LIMIT ?",
                (f"%{activity}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, activity, duration_min, notes, logged_at "
                "FROM sessions ORDER BY logged_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

    if not rows:
        return sanitize_for_telegram(
            "<i>No sessions found yet. Log your first session to start tracking!</i>"
        )

    lines = [f"<b>Recent sessions{' - ' + activity if activity else ''}</b>\n"]
    for sid, act, dur, notes, logged_at in rows:
        dur_label = f"{dur} min" if dur else "-"
        date_label = logged_at[:10]
        line = f"  [{sid}] <b>{act}</b> {dur_label} on {date_label}"
        if notes:
            line += f" - <i>{notes[:60]}</i>"
        lines.append(line)
    return sanitize_for_telegram("\n".join(lines))


@function_tool
async def get_activity_summary(activity: str) -> str:
    """Return total sessions, total minutes, and current consecutive-day streak for one activity.

    USE WHEN: the user asks for stats, a summary, their streak, or total time spent on an activity.

    Args:
        activity: The activity name to summarise (required).
    """
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration_min), 0) FROM sessions WHERE activity LIKE ?",
            (f"%{activity}%",),
        ).fetchone()
        total_sessions, total_min = row

        dates = conn.execute(
            "SELECT DISTINCT date(logged_at) FROM sessions WHERE activity LIKE ? ORDER BY 1 DESC",
            (f"%{activity}%",),
        ).fetchall()

    if total_sessions == 0:
        return sanitize_for_telegram(
            f"<i>No sessions found for <b>{activity}</b> yet.</i>"
        )

    # Compute consecutive-day streak from today backwards
    streak = 0
    today = datetime.now(timezone.utc).date()
    date_set = {r[0] for r in dates}
    check = today
    while str(check) in date_set:
        streak += 1
        check -= timedelta(days=1)

    hours = total_min // 60
    mins = total_min % 60
    time_label = f"{hours}h {mins}m" if hours else f"{mins}m"

    reply = (
        f"<b>{activity} - Summary</b>\n"
        f"Total sessions: <b>{total_sessions}</b>\n"
        f"Total time: <b>{time_label}</b>\n"
        f"Current streak: <b>{streak} day(s)</b>"
    )
    return sanitize_for_telegram(reply)


progress_tracker_agent = Agent(
    name="progress_tracker",
    instructions=SYSTEM_PROMPT,
    tools=[get_recent_sessions, get_activity_summary],
    model=get_model_for_bot("coachbot"),
    model_settings=ModelSettings(
        parallel_tool_calls=True,
        tool_choice="required",
        extra_body=get_openrouter_extra_body(),
    ),
)
