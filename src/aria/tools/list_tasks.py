"""
list_tasks - Lists tasks from the local SQLite store, filtered by status.
"""

from agents import function_tool
from aria.db import get_db


@function_tool
async def list_tasks(status: str = "open") -> str:
    """List tasks from the store, filtered by status.

    USE WHEN: The user asks what tasks they have, what is on their list, or
    wants to review open / completed work.

    Args:
        status: Filter by task status. One of 'open', 'done', or 'all'. Defaults to 'open'.
    """
    status = status.lower()
    if status not in ("open", "done", "all"):
        status = "open"

    with get_db() as conn:
        if status == "all":
            rows = conn.execute(
                """
                SELECT id, title, due_date, priority, status
                FROM tasks
                ORDER BY
                    CASE status WHEN 'open' THEN 0 ELSE 1 END,
                    CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    due_date IS NULL,
                    due_date
                LIMIT 20
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, title, due_date, priority, status
                FROM tasks
                WHERE status = ?
                ORDER BY
                    CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    due_date IS NULL,
                    due_date
                LIMIT 20
                """,
                (status,),
            ).fetchall()

    if not rows:
        return f"<i>No {status} tasks found.</i>"

    label = "Tasks" if status == "all" else f"{status.capitalize()} tasks"
    lines = [f"<b>{label}</b> ({len(rows)}):"]
    for row in rows:
        done_marker = "x" if row["status"] == "done" else " "
        due = f" | due {row['due_date']}" if row["due_date"] else ""
        lines.append(
            f"[{done_marker}] #{row['id']} {row['title']} (<i>{row['priority']}</i>{due})"
        )

    return "\n".join(lines)
