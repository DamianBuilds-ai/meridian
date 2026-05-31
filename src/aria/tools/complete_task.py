"""
complete_task - Marks a task as done in the local SQLite store.
"""

from agents import function_tool
from aria.db import get_db


@function_tool
async def complete_task(task_id: int) -> str:
    """Mark a task as completed.

    USE WHEN: The user says a task is done, finished, completed, or asks to check
    something off their list. Use the task ID shown in list_tasks output.

    Args:
        task_id: Numeric ID of the task to mark as done.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

        if not row:
            return f"<i>No task found with ID {task_id}.</i>"

        if row["status"] == "done":
            return f"<i>Task #{task_id} is already marked as done.</i>"

        conn.execute(
            "UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,)
        )
        conn.commit()

    return f"<b>Task #{task_id} completed</b>\n<i>{row['title']}</i>"
