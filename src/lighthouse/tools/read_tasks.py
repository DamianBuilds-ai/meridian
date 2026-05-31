"""
read_tasks - query open tasks across all domains from the Lighthouse SQLite store.

Tasks are written by other tools (or directly via SQL) and represent
cross-session work items. This tool is a read surface for the agent.
"""

from __future__ import annotations

import time

from agents import function_tool
from lighthouse._db import connect

VALID_STATUSES = {"open", "done", "cancelled", "all"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent", "all"}


@function_tool
async def read_tasks(
    domain: str = "all",
    status: str = "open",
    priority: str = "all",
    limit: int = 20,
) -> str:
    """List tasks stored in the Lighthouse task registry.

    USE WHEN: The user asks about pending work, open tasks, what needs doing,
    what tasks exist for a domain, or any to-do / action-item question.

    Args:
        domain:   Filter by domain name, or "all" for every domain.
        status:   Filter by status: open | done | cancelled | all. Default "open".
        priority: Filter by priority: low | normal | high | urgent | all. Default "all".
        limit:    Maximum number of rows to return. Default 20, max 100.
    """
    limit = min(max(1, limit), 100)
    status = status if status in VALID_STATUSES else "open"
    priority = priority if priority in VALID_PRIORITIES else "all"

    params: list = []
    where_clauses: list[str] = []

    if domain and domain != "all":
        where_clauses.append("domain = ?")
        params.append(domain)

    if status != "all":
        where_clauses.append("status = ?")
        params.append(status)

    if priority != "all":
        where_clauses.append("priority = ?")
        params.append(priority)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = connect()
    try:
        # Seed illustrative rows on first use so the bot can demo something
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            _seed_example_tasks(conn)

        rows = conn.execute(
            f"SELECT id, domain, title, priority, status, due_date, created_at "
            f"FROM tasks {where_sql} "
            f"ORDER BY "
            f"  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
            f"               WHEN 'normal' THEN 2 ELSE 3 END, "
            f"  created_at ASC "
            f"LIMIT ?",
            params + [limit],
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return f"<b>Tasks</b>\n\nNo tasks found (domain={domain}, status={status}, priority={priority})."

    lines = [f"<b>Tasks</b> (domain={domain}, status={status}, priority={priority})\n"]
    for r in rows:
        due = f"  due {r['due_date']}" if r["due_date"] else ""
        lines.append(
            f"[{r['id']}] <b>{r['title']}</b>\n"
            f"  domain=<code>{r['domain']}</code>  priority={r['priority']}  "
            f"status={r['status']}{due}"
        )

    return "\n".join(lines)


def _seed_example_tasks(conn) -> None:
    """Insert illustrative tasks so the demo works out-of-the-box.

    TODO: Remove this seed block once real tasks are being written by your bots.
          Tasks can be inserted via SQL or by adding a create_task tool to your bot.
    """
    now = int(time.time())
    examples = [
        ("assistant", "Review conversation quality logs for this week", "normal", "open", None),
        ("weather", "Add wind-speed field to daily briefing", "low", "open", "2026-06-07"),
        ("notes", "Prune duplicate entries older than 90 days", "high", "open", "2026-06-01"),
        ("general", "Update LIGHTHOUSE_DOMAINS_DIR path in docker-compose", "urgent", "open", "2026-05-31"),
        ("notes", "Archive completed meeting notes to cold storage", "normal", "done", None),
    ]
    for domain, title, priority, status, due_date in examples:
        conn.execute(
            "INSERT INTO tasks (domain, title, priority, status, due_date, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (domain, title, priority, status, due_date, now, now),
        )
