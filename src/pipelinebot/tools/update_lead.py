"""update_lead tool - advance pipeline stage or initiate two-phase contact deletion."""

from agents import function_tool
from pipelinebot._db import _conn

_VALID_STAGES = {"prospect", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"}

# Two-phase delete sentinel values (not real stages - intercepted by this tool)
_DELETE_REQUEST  = "DELETE_REQUEST"
_DELETE_CONFIRMED = "DELETE_CONFIRMED"


@function_tool
async def update_lead(
    contact_id: int,
    stage: str,
    notes: str = "",
) -> str:
    """Advance a contact's pipeline stage or initiate/confirm contact deletion.

    USE WHEN: the user says a deal moved forward, a prospect became qualified,
    a deal was won or lost, or the user wants to remove a contact.

    DELETION FLOW (two-phase, mandatory):
    - Phase 1: call with stage="DELETE_REQUEST" - marks contact as pending deletion and
      asks the user to confirm. Do not skip this step.
    - Phase 2: only after the user explicitly confirms, call again with stage="DELETE_CONFIRMED"
      to permanently remove the contact.
    - If the user cancels, call with stage="DELETE_CANCEL" to clear the pending flag.

    Valid stages: prospect, qualified, proposal, negotiation, closed_won, closed_lost.

    Args:
        contact_id: the integer ID from search_contacts.
        stage: new stage value, or DELETE_REQUEST / DELETE_CONFIRMED / DELETE_CANCEL.
        notes: optional notes to append (leave blank to keep existing notes).
    """
    with _conn() as con:
        contact = con.execute(
            "SELECT id, name, company, stage, notes, pending_delete FROM contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()

        if not contact:
            return f"<b>Error:</b> No contact with ID <code>{contact_id}</code>."

        name = contact["name"]
        company = contact["company"]

        # -- Phase 1: deletion request --
        if stage == _DELETE_REQUEST:
            con.execute(
                "UPDATE contacts SET pending_delete = 1 WHERE id = ?",
                (contact_id,),
            )
            return (
                f"<b>Deletion requested for {name} @ {company}</b>\n"
                f"Stage: <code>{contact['stage']}</code>\n\n"
                "To <b>permanently delete</b> this contact and all their interactions, "
                "reply 'yes, delete' and I will call update_lead with DELETE_CONFIRMED.\n"
                "To cancel, say 'cancel' and I will clear the pending flag."
            )

        # -- Phase 2: deletion confirmed --
        if stage == _DELETE_CONFIRMED:
            if not contact["pending_delete"]:
                return (
                    f"<b>Error:</b> {name} is not pending deletion. "
                    "Call update_lead with DELETE_REQUEST first."
                )
            con.execute("DELETE FROM followups WHERE contact_id = ?", (contact_id,))
            con.execute("DELETE FROM interactions WHERE contact_id = ?", (contact_id,))
            con.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            return f"<b>Contact deleted:</b> {name} @ {company} and all associated records have been permanently removed."

        # -- Cancel deletion --
        if stage == "DELETE_CANCEL":
            con.execute(
                "UPDATE contacts SET pending_delete = 0 WHERE id = ?",
                (contact_id,),
            )
            return f"<b>Deletion cancelled.</b> {name} @ {company} is still active."

        # -- Normal stage transition --
        if stage not in _VALID_STAGES:
            return (
                f"<b>Error:</b> '{stage}' is not a valid stage. "
                f"Valid stages: {sorted(_VALID_STAGES)}"
            )

        if contact["pending_delete"]:
            return (
                f"<b>Error:</b> {name} has a pending deletion request. "
                "Confirm or cancel deletion before making other changes."
            )

        old_stage = contact["stage"]
        new_notes = contact["notes"]
        if notes:
            new_notes = f"{new_notes}\n{notes}".strip()

        con.execute(
            "UPDATE contacts SET stage = ?, notes = ? WHERE id = ?",
            (stage, new_notes, contact_id),
        )

    return (
        f"<b>{name} @ {company} updated</b>\n"
        f"Stage: <code>{old_stage}</code> - <code>{stage}</code>"
        + (f"\nNotes appended: {notes}" if notes else "")
    )
