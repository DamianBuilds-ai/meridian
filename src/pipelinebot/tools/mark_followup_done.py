"""mark_followup_done tool - marks a follow-up item as completed."""

from agents import function_tool
from pipelinebot._db import _conn


@function_tool
async def mark_followup_done(followup_id: int) -> str:
    """Mark a specific follow-up action as completed so it leaves the action queue.

    USE WHEN: the user says they completed an action, ticked off a task, or asks to
    clear / close / done a follow-up item. The followup_id is shown in list_pipeline output.

    Args:
        followup_id: the integer ID of the follow-up item from list_pipeline output.
    """
    with _conn() as con:
        row = con.execute(
            """
            SELECT f.id, f.action, f.due_date, c.name, c.company
            FROM followups f
            JOIN contacts c ON c.id = f.contact_id
            WHERE f.id = ? AND f.done = 0
            """,
            (followup_id,),
        ).fetchone()

        if not row:
            # Check if it already exists but is done
            exists = con.execute(
                "SELECT id FROM followups WHERE id = ?", (followup_id,)
            ).fetchone()
            if exists:
                return f"<b>Follow-up <code>{followup_id}</code> is already marked done.</b>"
            return f"<b>Error:</b> No open follow-up with ID <code>{followup_id}</code>. Check list_pipeline for current IDs."

        con.execute("UPDATE followups SET done = 1 WHERE id = ?", (followup_id,))

    return (
        f"<b>Done:</b> Follow-up <code>{followup_id}</code> cleared.\n"
        f"Contact: {row['name']} @ {row['company']}\n"
        f"Action completed: {row['action']}"
    )
