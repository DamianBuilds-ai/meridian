"""set_followup tool - schedule or reschedule a follow-up action for a contact."""

import datetime
from agents import function_tool
from pipelinebot._db import _conn


@function_tool
async def set_followup(
    contact_id: int,
    due_date: str,
    action: str,
    replace_existing: bool = False,
) -> str:
    """Schedule a follow-up action for a contact on a specific date.

    USE WHEN: the user wants to set a reminder, reschedule a follow-up, or
    book a next-action for a contact at a specific date ("follow up with Ben on Friday",
    "remind me about Acme next Tuesday").

    Args:
        contact_id: the integer ID from search_contacts.
        due_date: ISO date string (YYYY-MM-DD) for the follow-up.
        action: what needs to happen (e.g. "Call to discuss updated proposal").
        replace_existing: if True, mark all existing undone follow-ups for this contact
                          as done before creating the new one (use when rescheduling).
    """
    try:
        parsed = datetime.date.fromisoformat(due_date)
    except ValueError:
        return f"<b>Error:</b> due_date must be YYYY-MM-DD format, got '{due_date}'."

    if not action.strip():
        return "<b>Error:</b> action cannot be empty."

    today = datetime.date.today()
    if parsed < today:
        return (
            f"<b>Warning:</b> {due_date} is in the past. "
            "Use a future date or call list_pipeline to review overdue items."
        )

    with _conn() as con:
        contact = con.execute(
            "SELECT id, name, company FROM contacts WHERE id = ? AND pending_delete = 0",
            (contact_id,),
        ).fetchone()
        if not contact:
            return f"<b>Error:</b> No active contact with ID <code>{contact_id}</code>."

        if replace_existing:
            con.execute(
                "UPDATE followups SET done = 1 WHERE contact_id = ? AND done = 0",
                (contact_id,),
            )

        con.execute(
            "INSERT INTO followups (contact_id, due_date, action) VALUES (?, ?, ?)",
            (contact_id, due_date, action.strip()),
        )

    replaced_msg = " (previous follow-ups cleared)" if replace_existing else ""
    return (
        f"<b>Follow-up scheduled{replaced_msg}</b>\n"
        f"Contact: {contact['name']} @ {contact['company']}\n"
        f"Date: <code>{due_date}</code>\n"
        f"Action: {action.strip()}"
    )
