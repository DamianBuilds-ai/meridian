"""list_pipeline tool - returns today's action queue from the pipeline."""

import datetime
from agents import function_tool
from pipelinebot._db import _conn


@function_tool
async def list_pipeline(show_all: bool = False) -> str:
    """Return today's action queue: contacts with follow-ups due today (or all open follow-ups).

    USE WHEN: the user asks "what's on my plate today", "show pipeline", "what do I need to do",
    or any request for a daily summary or action list.

    Args:
        show_all: if True, return all undone follow-ups regardless of date; default False (today only).
    """
    today = datetime.date.today().isoformat()

    with _conn() as con:
        if show_all:
            rows = con.execute(
                """
                SELECT f.id, f.due_date, f.action, c.name, c.company, c.stage, c.email
                FROM followups f
                JOIN contacts c ON c.id = f.contact_id
                WHERE f.done = 0 AND c.pending_delete = 0
                ORDER BY f.due_date, c.name
                """,
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT f.id, f.due_date, f.action, c.name, c.company, c.stage, c.email
                FROM followups f
                JOIN contacts c ON c.id = f.contact_id
                WHERE f.done = 0 AND f.due_date <= ? AND c.pending_delete = 0
                ORDER BY f.due_date, c.name
                """,
                (today,),
            ).fetchall()

    if not rows:
        return "<b>Pipeline clear</b> - no follow-ups due today." if not show_all else "<b>Pipeline clear</b> - no open follow-ups."

    label = "Today's Action Queue" if not show_all else "All Open Follow-Ups"
    lines = [f"<b>{label}</b> ({len(rows)} item{'s' if len(rows) != 1 else ''}):\n"]
    for r in rows:
        overdue = " <i>(overdue)</i>" if r["due_date"] < today else ""
        lines.append(
            f"- <b>{r['name']}</b> @ {r['company']} [{r['stage']}]{overdue}\n"
            f"  Action: {r['action']}\n"
            f"  Due: <code>{r['due_date']}</code>  |  follow-up ID: <code>{r['id']}</code>"
        )

    return "\n".join(lines)
