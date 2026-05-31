"""
warm_start - Hydrates the session with the most recent context from the local store.
This tool MUST be called at the very beginning of every session.
"""

from agents import function_tool
from shared.dates import local_now, format_datetime
from aria.db import get_db


@function_tool
async def warm_start() -> str:
    """Load recent session context, open tasks, and top notes to ground this session.

    USE WHEN: Always call this tool FIRST, before answering any user request. It
    restores recent memory so you can give context-aware replies without asking
    the user to repeat themselves.
    """
    now_str = format_datetime(local_now())

    with get_db() as conn:
        # Last saved session summary
        ctx_row = conn.execute(
            "SELECT summary, saved_at FROM session_context ORDER BY id DESC LIMIT 1"
        ).fetchone()

        # Up to 5 open tasks ordered by priority weight then due date
        open_tasks = conn.execute(
            """
            SELECT id, title, due_date, priority
            FROM tasks
            WHERE status = 'open'
            ORDER BY
                CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                due_date IS NULL,
                due_date
            LIMIT 5
            """
        ).fetchall()

        # 3 most recent notes
        recent_notes = conn.execute(
            "SELECT id, title, tags FROM notes ORDER BY id DESC LIMIT 3"
        ).fetchall()

    lines: list[str] = [f"<b>Session warm-start</b> ({now_str})"]

    if ctx_row:
        lines.append(f"\n<b>Last session summary</b> (saved {ctx_row['saved_at']}):")
        lines.append(ctx_row["summary"])
    else:
        lines.append("\n<i>No previous session context found - this looks like a fresh install.</i>")

    if open_tasks:
        lines.append("\n<b>Open tasks</b>:")
        for t in open_tasks:
            due = f" - due {t['due_date']}" if t["due_date"] else ""
            lines.append(f"  [{t['id']}] {t['title']} (<i>{t['priority']}</i>{due})")
    else:
        lines.append("\n<i>No open tasks.</i>")

    if recent_notes:
        lines.append("\n<b>Recent notes</b>:")
        for n in recent_notes:
            tags = f" [{n['tags']}]" if n["tags"] else ""
            lines.append(f"  [{n['id']}] {n['title']}{tags}")

    lines.append("\n<i>Context loaded. Ready to assist.</i>")

    return "\n".join(lines)
