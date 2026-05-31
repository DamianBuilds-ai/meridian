"""search_contacts tool - fuzzy contact lookup by name or company."""

from agents import function_tool
from shared.fuzzy import fuzzy_match
from pipelinebot._db import _conn


@function_tool
async def search_contacts(query: str, include_closed: bool = False) -> str:
    """Find contacts by name or company using fuzzy matching.

    USE WHEN: the user refers to a contact informally ("the Acme guy", "Ben from Bright"),
    or asks to look up / find / search for a contact before taking any action on them.
    Always call this before log_call, update_lead, draft_email, set_followup, or compute_quote
    so you have the correct contact ID.

    Args:
        query: free-text name or company fragment to search for.
        include_closed: if True, include closed_won and closed_lost contacts; default False.
    """
    with _conn() as con:
        rows = con.execute(
            "SELECT id, name, company, email, phone, stage, notes FROM contacts WHERE pending_delete = 0"
        ).fetchall()

    contacts = [dict(r) for r in rows]
    if not include_closed:
        contacts = [c for c in contacts if c["stage"] not in ("closed_won", "closed_lost")]

    # fuzzy_match expects list[dict] with a "name" key; we score against name + company
    # by building a merged search target per record.
    for c in contacts:
        c["_search_name"] = f"{c['name']} {c['company']}"

    # Run fuzzy match against name+company merged field
    search_targets = [{"name": c["_search_name"], **c} for c in contacts]
    best = fuzzy_match(query, search_targets, threshold=0.25)

    if not best:
        # Fall back: list all contacts so the user can pick
        if not contacts:
            return "<b>No contacts found.</b> Add contacts via your CRM import."
        names = "\n".join(f"- <b>{c['name']}</b> @ {c['company']} (ID: <code>{c['id']}</code>, stage: {c['stage']})" for c in contacts[:10])
        return f"<b>No close match for '{query}'.</b> Available contacts:\n{names}"

    c = best
    last_interaction = _get_last_interaction(c["id"])
    return (
        f"<b>{c['name']}</b> @ {c['company']}\n"
        f"Stage: <code>{c['stage']}</code>\n"
        f"Email: {c['email'] or '(none)'}\n"
        f"Phone: {c['phone'] or '(none)'}\n"
        f"Notes: {c['notes'] or '(none)'}\n"
        f"Contact ID: <code>{c['id']}</code>\n"
        f"{last_interaction}"
    )


def _get_last_interaction(contact_id: int) -> str:
    with _conn() as con:
        row = con.execute(
            "SELECT type, summary, outcome, logged_at FROM interactions WHERE contact_id = ? ORDER BY logged_at DESC LIMIT 1",
            (contact_id,),
        ).fetchone()
    if not row:
        return "Last interaction: <i>none on record</i>"
    return (
        f"Last interaction: <code>{row['logged_at'][:10]}</code> - {row['type']} - {row['outcome'] or row['summary']}"
    )
