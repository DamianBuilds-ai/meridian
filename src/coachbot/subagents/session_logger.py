"""
Sub-agent: session_logger
Records a single activity practice session to the SQLite store.
"""

import os
import sqlite3
from datetime import datetime, timezone

from agents import Agent, ModelSettings, function_tool
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body
from shared.telegram_format import sanitize_for_telegram

_DB_PATH = os.getenv("COACHBOT_DB_PATH", "./coachbot.db")

SYSTEM_PROMPT = """You are Session Logger, a specialist sub-agent for the CoachBot activity tracker.

Your ONLY job is to record a practice session using the <b>log_session</b> tool.

Telegram HTML ONLY: <b>bold</b>, <i>italic</i>, <code>mono</code>.
BANNED: **bold** *italic* `code` # headers.

Rules:
- Always call log_session with the details the user provided.
- If a required field is missing, use a sensible default and note it in your reply.
- Never answer from memory; always call the tool.
- Confirm success with the stored session ID and a brief summary.
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
async def log_session(
    activity: str,
    duration_min: int = 0,
    notes: str = "",
) -> str:
    """Record a completed practice session for the given activity.

    USE WHEN: the user describes finishing a session, practice, drill, or run.

    Args:
        activity:     Name of the activity or skill practised (e.g. "guitar", "chess").
        duration_min: How many minutes the session lasted (0 if unknown).
        notes:        Optional free-text notes about what was worked on.
    """
    logged_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(_DB_PATH) as conn:
        _ensure_schema(conn)
        cur = conn.execute(
            "INSERT INTO sessions (activity, duration_min, notes, logged_at) VALUES (?, ?, ?, ?)",
            (activity, duration_min, notes, logged_at),
        )
        session_id = cur.lastrowid
        conn.commit()

    duration_label = f"{duration_min} min" if duration_min else "duration not recorded"
    reply = (
        f"<b>Session logged</b> (ID {session_id})\n"
        f"Activity: <b>{activity}</b>\n"
        f"Duration: {duration_label}\n"
        + (f"Notes: <i>{notes}</i>\n" if notes else "")
        + f"<code>{logged_at[:19]} UTC</code>"
    )
    return sanitize_for_telegram(reply)


session_logger_agent = Agent(
    name="session_logger",
    instructions=SYSTEM_PROMPT,
    tools=[log_session],
    model=get_model_for_bot("coachbot"),
    model_settings=ModelSettings(
        parallel_tool_calls=True,
        tool_choice="required",
        extra_body=get_openrouter_extra_body(),
    ),
)
