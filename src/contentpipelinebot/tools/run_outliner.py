"""Tool: invoke the outliner sub-agent on a transcript."""

import os
import sqlite3
from agents import function_tool, Runner
from shared.telegram_format import sanitize_for_telegram

_DB_PATH = os.getenv("CONTENT_PIPELINE_DB_PATH", "/tmp/contentpipelinebot.db")


def _ensure_db() -> sqlite3.Connection:
    """Open (or create) the SQLite DB and ensure the results table exists."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT NOT NULL,
            stage       TEXT NOT NULL,
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


@function_tool
async def run_outliner(transcript: str, run_id: str = "") -> str:
    """Generate a hierarchical outline from the provided transcript text.

    USE WHEN: the user asks for an outline, structure, or table of contents
    from a transcript or text blob.

    Args:
        transcript: the full transcript or text to outline
        run_id: optional identifier for this pipeline run (used to group results)
    """
    from contentpipelinebot.subagents.outliner import outliner_agent

    result = await Runner.run(starting_agent=outliner_agent, input=transcript)
    outline = result.final_output or "(no outline produced)"

    if run_id:
        conn = _ensure_db()
        conn.execute(
            "INSERT INTO pipeline_results (run_id, stage, content) VALUES (?, ?, ?)",
            (run_id, "outline", outline),
        )
        conn.commit()
        conn.close()

    safe = sanitize_for_telegram(outline)
    return f"<b>Outline</b>\n\n{safe}"
