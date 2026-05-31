"""
read_findings - browse cross-component notes by component and/or category.

Unlike search_memory (which does keyword FTS), read_findings returns the most
recent N findings for a component/category combination. Use it when the user
wants to browse all notes for a component, not search for a specific phrase.
"""

from __future__ import annotations

import time

from agents import function_tool
from lighthouse._db import connect

VALID_CATEGORIES = {"note", "alert", "decision", "action", "all"}


@function_tool
async def read_findings(
    component: str = "all",
    category: str = "all",
    limit: int = 15,
) -> str:
    """Browse recent cross-component findings stored in Lighthouse.

    USE WHEN: The user asks to see all notes for a component ("show me weather notes"),
    browse recent alerts ("what alerts have come in?"), or review decisions ("list decisions").
    Use search_memory instead when the user gives a keyword or phrase to search for.

    Args:
        component: Component/domain name to filter by, or "all" for every component.
        category:  Category filter: note | alert | decision | action | all. Default "all".
        limit:     Maximum rows to return. Default 15, max 50.
    """
    limit = min(max(1, limit), 50)
    category = category if category in VALID_CATEGORIES else "all"

    params: list = []
    where_clauses: list[str] = []

    if component and component != "all":
        where_clauses.append("component = ?")
        params.append(component)

    if category != "all":
        where_clauses.append("category = ?")
        params.append(category)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = connect()
    try:
        # Ensure example data exists for demo purposes
        count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        if count == 0:
            _seed_if_empty(conn)

        rows = conn.execute(
            f"SELECT id, component, category, body, created_at "
            f"FROM findings {where_sql} "
            f"ORDER BY created_at DESC "
            f"LIMIT ?",
            params + [limit],
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return (
            f"<b>Findings</b>\n\n"
            f"No findings for component=<code>{component}</code> "
            f"category=<code>{category}</code>."
        )

    lines = [f"<b>Findings</b> (component={component}, category={category})\n"]
    for r in rows:
        ts = _fmt_ts(r["created_at"])
        body = (r["body"] or "")[:400]
        lines.append(
            f"[{r['id']}] <b>{r['component']}</b> <i>[{r['category']}]</i>  {ts}\n"
            f"  {body}"
        )

    return "\n\n".join(lines)


def _fmt_ts(ts: int) -> str:
    from datetime import datetime, timezone
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _seed_if_empty(conn) -> None:
    """Seed illustrative findings when the store is empty.

    TODO: Remove once real findings are written via record_finding. See docs/adding-a-bot.md.
    """
    now = int(time.time())
    rows = [
        ("assistant", "decision", "Switched model to gpt-4o-mini. Approved 2026-05-20."),
        ("weather", "alert", "Rate limit hit on 2026-05-29. Backoff added."),
        ("notes", "note", "Voice-to-text via Groq Whisper. Language auto-detected."),
        ("general", "action", "All bots should write health JSON to LIGHTHOUSE_DOMAINS_DIR."),
    ]
    for component, category, body in rows:
        conn.execute(
            "INSERT INTO findings (component, category, body, created_at) "
            "VALUES (?, ?, ?, ?)",
            (component, category, body, now),
        )
