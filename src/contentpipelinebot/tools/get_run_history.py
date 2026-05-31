"""Tool: retrieve stored pipeline results from SQLite."""

import os
import sqlite3
from agents import function_tool
from shared.telegram_format import sanitize_for_telegram

_DB_PATH = os.getenv("CONTENT_PIPELINE_DB_PATH", "/tmp/contentpipelinebot.db")


@function_tool
async def get_run_history(run_id: str = "", limit: int = 10) -> str:
    """Retrieve past pipeline results stored in the local SQLite database.

    USE WHEN: the user asks to see previous results, recall a past run,
    or check what was produced for a specific run_id.

    Args:
        run_id: optional run identifier to filter results; omit to list recent runs
        limit:  maximum number of rows to return (default 10, max 50)
    """
    limit = min(max(1, limit), 50)

    if not os.path.exists(_DB_PATH):
        return "<i>No pipeline history found yet. Run the pipeline on a transcript first.</i>"

    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row

    if run_id:
        rows = conn.execute(
            "SELECT run_id, stage, content, created_at FROM pipeline_results "
            "WHERE run_id = ? ORDER BY id DESC LIMIT ?",
            (run_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT run_id, stage, content, created_at FROM pipeline_results "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()

    if not rows:
        return "<i>No results found.</i>"

    lines = []
    for row in rows:
        preview = sanitize_for_telegram(row["content"][:200])
        lines.append(
            f"<b>[{row['run_id'] or 'no-id'}] {row['stage']}</b> "
            f"<i>{row['created_at']}</i>\n{preview}..."
        )

    return "\n\n".join(lines)
