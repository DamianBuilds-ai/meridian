"""
create_task - Adds a new task to the local SQLite task store.
"""

from agents import function_tool
from shared.dates import local_now, to_iso
from aria.db import get_db


@function_tool
async def create_task(
    title: str,
    due_date: str = "",
    priority: str = "medium",
) -> str:
    """Create a new task and persist it to the local store.

    USE WHEN: The user asks to add, create, or remember a task, to-do, or action item.

    Args:
        title:    Short description of the task. Required.
        due_date: Optional due date in YYYY-MM-DD format. Leave empty if none given.
        priority: Task priority - 'high', 'medium', or 'low'. Defaults to 'medium'.
    """
    # Normalise priority
    priority = priority.lower() if priority.lower() in ("high", "medium", "low") else "medium"
    created = to_iso(local_now())

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, due_date, priority, status, created) VALUES (?, ?, ?, 'open', ?)",
            (title, due_date or None, priority, created),
        )
        task_id = cursor.lastrowid
        conn.commit()

    due_str = f" - due <code>{due_date}</code>" if due_date else ""
    return (
        f"<b>Task created</b> [#{task_id}]\n"
        f"{title}\n"
        f"Priority: <i>{priority}</i>{due_str}"
    )
