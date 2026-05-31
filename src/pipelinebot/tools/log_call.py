"""log_call tool - records a structured call interaction from plain-English notes."""

import datetime
from agents import function_tool
from pipelinebot._db import _conn


_VALID_TYPES = {"call", "email", "meeting", "demo", "other"}
_VALID_OUTCOMES = {"positive", "neutral", "negative", "no_answer", "left_voicemail"}


@function_tool
async def log_call(
    contact_id: int,
    interaction_type: str,
    summary: str,
    outcome: str,
    next_action: str,
    followup_date: str = "",
) -> str:
    """Record a structured interaction (call, email, meeting, demo) for a contact.

    USE WHEN: the user says they spoke to someone, had a meeting, sent an email,
    or wants to log a touch-point. Parse the user's natural language note into the
    structured fields before calling this tool.

    Args:
        contact_id: the integer ID from search_contacts.
        interaction_type: one of: call, email, meeting, demo, other.
        summary: one or two sentences summarising what was discussed.
        outcome: one of: positive, neutral, negative, no_answer, left_voicemail.
        next_action: the agreed or planned next step (e.g. "Send proposal by Friday").
        followup_date: ISO date (YYYY-MM-DD) for when to follow up. Leave empty to
                       skip scheduling; the user can call set_followup separately.
    """
    interaction_type = interaction_type.lower().strip()
    outcome = outcome.lower().strip()

    if interaction_type not in _VALID_TYPES:
        return f"<b>Error:</b> interaction_type must be one of {sorted(_VALID_TYPES)}."
    if outcome not in _VALID_OUTCOMES:
        return f"<b>Error:</b> outcome must be one of {sorted(_VALID_OUTCOMES)}."

    with _conn() as con:
        contact = con.execute(
            "SELECT id, name, company FROM contacts WHERE id = ? AND pending_delete = 0",
            (contact_id,),
        ).fetchone()
        if not contact:
            return f"<b>Error:</b> No active contact with ID <code>{contact_id}</code>."

        con.execute(
            """
            INSERT INTO interactions (contact_id, type, summary, outcome, next_action)
            VALUES (?, ?, ?, ?, ?)
            """,
            (contact_id, interaction_type, summary, outcome, next_action),
        )

        followup_msg = ""
        if followup_date:
            try:
                datetime.date.fromisoformat(followup_date)
            except ValueError:
                return f"<b>Error:</b> followup_date must be YYYY-MM-DD format, got '{followup_date}'."
            con.execute(
                "INSERT INTO followups (contact_id, due_date, action) VALUES (?, ?, ?)",
                (contact_id, followup_date, next_action),
            )
            followup_msg = f"\nFollow-up scheduled for <code>{followup_date}</code>."

    return (
        f"<b>Interaction logged</b> for {contact['name']} @ {contact['company']}\n"
        f"Type: <code>{interaction_type}</code>  |  Outcome: <code>{outcome}</code>\n"
        f"Summary: {summary}\n"
        f"Next action: {next_action}"
        f"{followup_msg}"
    )
