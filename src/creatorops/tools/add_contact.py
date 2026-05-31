"""Add a new contact to the CreatorOps CRM."""

from agents import function_tool
from creatorops.tools.db import get_conn


@function_tool
async def add_contact(
    name: str,
    email: str = "",
    platform: str = "",
    notes: str = "",
) -> str:
    """Save a new contact to the CRM.

    USE WHEN: the user wants to record a new person they met, a collaborator,
    a potential sponsor, or anyone they want to stay in touch with.

    Args:
        name: full name of the contact
        email: email address (optional)
        platform: primary platform, e.g. "Instagram", "LinkedIn", "YouTube"
        notes: any context notes about this person
    """
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO contacts (name, email, platform, notes)
            VALUES (?, ?, ?, ?)
            """,
            (name, email or None, platform or None, notes or None),
        )
        contact_id = cursor.lastrowid

    lines = [
        f"<b>Contact saved</b> (id {contact_id})",
        f"<b>Name:</b> {name}",
    ]
    if email:
        lines.append(f"<b>Email:</b> {email}")
    if platform:
        lines.append(f"<b>Platform:</b> {platform}")
    if notes:
        lines.append(f"<b>Notes:</b> {notes}")
    return "\n".join(lines)
