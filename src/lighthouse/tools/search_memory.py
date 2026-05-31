"""
search_memory - keyword search over the Lighthouse long-term memory store.

Primary path: SQLite FTS5 full-text search (ranked, fast).
Fallback path: LIKE scan on findings.body (used if FTS5 was not compiled in).

The memory store is populated by record_finding and by any other tool or
bot that inserts rows into the findings table. This tool is a pure read surface.
"""

from __future__ import annotations

import sqlite3
import time

from agents import function_tool
from lighthouse._db import connect


@function_tool
async def search_memory(query: str, limit: int = 10) -> str:
    """Search the Lighthouse memory store for past findings, notes, and decisions.

    USE WHEN: The user asks "do we know anything about X?", "what was decided about Y?",
    "has this come up before?", "find notes on Z", "what do I remember about...",
    or any recall / memory-lookup question.

    Args:
        query: Keyword or phrase to search for. Can be a single word or a short phrase.
        limit: Maximum results to return. Default 10, max 50.
    """
    limit = min(max(1, limit), 50)
    query = (query or "").strip()
    if not query:
        return "<b>Memory Search</b>\n\nPlease provide a search query."

    conn = connect()
    try:
        count = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        if count == 0:
            _seed_example_findings(conn)

        rows = _fts_search(conn, query, limit)
        if rows is None:
            rows = _like_search(conn, query, limit)
    finally:
        conn.close()

    if not rows:
        return (
            f"<b>Memory Search</b>: <code>{query}</code>\n\n"
            "No matching records found."
        )

    lines = [f"<b>Memory Search</b>: <code>{query}</code>\n"]
    for r in rows:
        ts = _fmt_ts(r.get("created_at") or 0)
        component = r.get("component", "")
        category = r.get("category", "note")
        body = (r.get("body") or "")[:300]
        lines.append(
            f"[{r['id']}] <b>{component}</b> [{category}]  <i>{ts}</i>\n"
            f"  {body}"
        )

    return "\n\n".join(lines)


def _fts_search(conn: sqlite3.Connection, query: str, limit: int) -> list[dict] | None:
    """FTS5 ranked search. Returns None if FTS5 is not available."""
    try:
        rows = conn.execute(
            "SELECT f.id, f.component, f.category, f.body, f.created_at "
            "FROM memory_fts m "
            "JOIN findings f ON f.id = m.rowid "
            "WHERE memory_fts MATCH ? "
            "ORDER BY rank "
            "LIMIT ?",
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return None  # FTS5 not available


def _like_search(conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
    """Fallback LIKE scan when FTS5 is unavailable."""
    pattern = f"%{query}%"
    rows = conn.execute(
        "SELECT id, component, category, body, created_at "
        "FROM findings "
        "WHERE body LIKE ? OR component LIKE ? "
        "ORDER BY created_at DESC "
        "LIMIT ?",
        (pattern, pattern, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _fmt_ts(ts: int) -> str:
    from datetime import datetime, timezone
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _seed_example_findings(conn: sqlite3.Connection) -> None:
    """Insert illustrative memory entries so the demo works out-of-the-box.

    TODO: Remove this seed block once real findings are being written via record_finding.
    """
    now = int(time.time())
    examples = [
        ("assistant", "decision", "Switched model from gpt-4o to gpt-4o-mini to reduce latency. Approved 2026-05-20."),
        ("weather", "alert", "OpenWeatherMap API rate limit hit on 2026-05-29. Added exponential backoff."),
        ("notes", "note", "Notes bot handles voice-to-text via Groq Whisper. Language auto-detected."),
        ("general", "action", "All bots should write a health JSON to LIGHTHOUSE_DOMAINS_DIR on startup."),
        ("assistant", "note", "Telegram HTML only policy enforced in system prompt v3. Markdown no longer leaks."),
    ]
    for component, category, body in examples:
        conn.execute(
            "INSERT INTO findings (component, category, body, created_at) "
            "VALUES (?, ?, ?, ?)",
            (component, category, body, now),
        )
