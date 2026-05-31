"""Tool: delete a logged shift by ID (user-scoped for safety)."""

from agents import function_tool
from shiftbot.db import get_conn


@function_tool
async def delete_shift(user_id: str, shift_id: int) -> str:
    """Remove a previously logged shift by its numeric ID.

    USE WHEN: the user wants to delete a mistakenly logged shift or
    correct an entry by removing and re-logging it.

    Args:
        user_id:  Telegram user ID string. Only the owner can delete
                  their own shifts (prevents cross-user data deletion).
        shift_id: The numeric shift ID shown in list_shifts output.
    """
    with get_conn() as conn:
        # Verify ownership before deletion
        row = conn.execute(
            "SELECT id, shift_date, platform FROM shifts WHERE id = ? AND user_id = ?",
            (shift_id, user_id),
        ).fetchone()

        if not row:
            return (
                f"Shift <code>#{shift_id}</code> not found or does not belong to your account."
            )

        conn.execute("DELETE FROM shifts WHERE id = ? AND user_id = ?", (shift_id, user_id))

    return (
        f"Shift <code>#{shift_id}</code> deleted.\n"
        f"({row['shift_date']} - {row['platform']})"
    )
