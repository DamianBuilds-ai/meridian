"""
record_finding - write a cross-component note, alert, decision, or action item
into the Lighthouse long-term memory store.

This is the write surface. Findings are immediately searchable via search_memory
and browsable via read_findings. The FTS5 trigger keeps the index in sync.
"""

from __future__ import annotations

from agents import function_tool
from lighthouse._db import connect

VALID_CATEGORIES = {"note", "alert", "decision", "action"}


@function_tool
async def record_finding(
    component: str,
    body: str,
    category: str = "note",
) -> str:
    """Save a note, alert, decision, or action item to the Lighthouse memory store.

    USE WHEN: The user wants to save something for later ("remember that...",
    "make a note", "log this decision", "record this alert", "save this for next session").
    Also use when summarizing a resolved issue that should be preserved as institutional memory.

    Args:
        component: Which component/domain this finding belongs to (e.g. "assistant", "weather").
                   Use "general" for stack-wide notes.
        body:      The full text of the finding. Be specific and self-contained - this record
                   must make sense when read in a future session without extra context.
        category:  note | alert | decision | action. Default "note".
                   - note:     general observation or background info
                   - alert:    something that went wrong or needs attention
                   - decision: a choice made and why
                   - action:   a concrete next step or commitment
    """
    component = (component or "general").strip()
    body = (body or "").strip()
    if not body:
        return "<b>Record Finding</b>\n\nBody cannot be empty."

    if category not in VALID_CATEGORIES:
        category = "note"

    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO findings (component, category, body) VALUES (?, ?, ?)",
            (component, category, body),
        )
        row_id = cur.lastrowid
    finally:
        conn.close()

    return (
        f"<b>Finding saved</b> [id={row_id}]\n"
        f"  component: <code>{component}</code>\n"
        f"  category:  <code>{category}</code>\n"
        f"  body: {body[:200]}{'...' if len(body) > 200 else ''}"
    )
