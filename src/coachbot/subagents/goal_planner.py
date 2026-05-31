"""
Sub-agent: goal_planner
Creates, lists, and marks goals for an activity using the SQLite store.
"""

import os
import sqlite3
from datetime import datetime, timezone

from agents import Agent, ModelSettings, function_tool
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body
from shared.telegram_format import sanitize_for_telegram

_DB_PATH = os.getenv("COACHBOT_DB_PATH", "./coachbot.db")

SYSTEM_PROMPT = """You are Goal Planner, a specialist sub-agent for the CoachBot activity tracker.

Your ONLY job is to create, list, and complete goals using the available tools.

Telegram HTML ONLY: <b>bold</b>, <i>italic</i>, <code>mono</code>.
BANNED: **bold** *italic* `code` # headers.

Rules:
- Always call a tool first; never answer from memory.
- When creating a goal, confirm what was saved.
- When listing goals, group open and completed goals separately.
- When marking complete, confirm the goal ID and description.
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            activity     TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            target_date  TEXT    NOT NULL DEFAULT '',
            completed    INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL
        )
    """)
    conn.commit()


@function_tool
async def create_goal(
    activity: str,
    description: str,
    target_date: str = "",
) -> str:
    """Save a new goal for an activity.

    USE WHEN: the user wants to set a target, goal, or milestone for an activity.

    Args:
        activity:    The activity this goal belongs to (e.g. "guitar").
        description: What the goal is (e.g. "Learn the C major scale").
        target_date: Optional target date in YYYY-MM-DD format.
    """
    created_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "INSERT INTO goals (activity, description, target_date, completed, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (activity, description, target_date, created_at),
        )
        goal_id = cur.lastrowid
        conn.commit()

    date_label = f" by <b>{target_date}</b>" if target_date else ""
    reply = (
        f"<b>Goal saved</b> (ID {goal_id})\n"
        f"Activity: <b>{activity}</b>\n"
        f"Goal: {description}{date_label}"
    )
    return sanitize_for_telegram(reply)


@function_tool
async def list_goals(activity: str = "", include_completed: bool = False) -> str:
    """List goals, optionally filtered by activity or completion status.

    USE WHEN: the user asks to see their goals, targets, or what they are working towards.

    Args:
        activity:          Filter by activity name. Empty returns all activities.
        include_completed: Set True to also show completed goals (default: open only).
    """
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        base = (
            "SELECT id, activity, description, target_date, completed "
            "FROM goals WHERE 1=1"
        )
        params: list = []
        if activity:
            base += " AND activity LIKE ?"
            params.append(f"%{activity}%")
        if not include_completed:
            base += " AND completed = 0"
        base += " ORDER BY activity, completed, created_at"
        rows = conn.execute(base, params).fetchall()

    if not rows:
        label = f" for <b>{activity}</b>" if activity else ""
        return sanitize_for_telegram(f"<i>No goals found{label}. Use 'set goal' to add one.</i>")

    open_lines = []
    done_lines = []
    for gid, act, desc, tdate, completed in rows:
        date_suffix = f" (by {tdate})" if tdate else ""
        entry = f"  [{gid}] <b>{act}</b> - {desc}{date_suffix}"
        if completed:
            done_lines.append(f"<s>{entry}</s>")
        else:
            open_lines.append(entry)

    parts = []
    if open_lines:
        parts.append("<b>Open goals</b>\n" + "\n".join(open_lines))
    if done_lines:
        parts.append("<b>Completed goals</b>\n" + "\n".join(done_lines))

    return sanitize_for_telegram("\n\n".join(parts))


@function_tool
async def complete_goal(goal_id: int) -> str:
    """Mark a goal as completed.

    USE WHEN: the user says they achieved or completed a goal, or wants to tick one off.

    Args:
        goal_id: The numeric ID of the goal to mark complete (shown in list_goals).
    """
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT description, activity, completed FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()
        if not row:
            return sanitize_for_telegram(f"<i>No goal found with ID {goal_id}.</i>")
        desc, activity, already_done = row
        if already_done:
            return sanitize_for_telegram(
                f"<i>Goal {goal_id} (<b>{desc}</b>) is already marked complete.</i>"
            )
        conn.execute("UPDATE goals SET completed = 1 WHERE id = ?", (goal_id,))
        conn.commit()

    reply = (
        f"<b>Goal completed!</b>\n"
        f"Activity: <b>{activity}</b>\n"
        f"Goal: {desc}\n"
        f"Nice work - goal {goal_id} is done."
    )
    return sanitize_for_telegram(reply)


goal_planner_agent = Agent(
    name="goal_planner",
    instructions=SYSTEM_PROMPT,
    tools=[create_goal, list_goals, complete_goal],
    model=get_model_for_bot("coachbot"),
    model_settings=ModelSettings(
        parallel_tool_calls=True,
        tool_choice="required",
        extra_body=get_openrouter_extra_body(),
    ),
)
