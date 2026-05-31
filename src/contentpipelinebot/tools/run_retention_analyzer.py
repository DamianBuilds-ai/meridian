"""Tool: invoke the retention_analyzer sub-agent on a transcript."""

import os
import sqlite3
from agents import function_tool, Runner
from shared.telegram_format import sanitize_for_telegram

_DB_PATH = os.getenv("CONTENT_PIPELINE_DB_PATH", "/tmp/contentpipelinebot.db")


def _ensure_db() -> sqlite3.Connection:
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
async def run_retention_analyzer(transcript: str, run_id: str = "") -> str:
    """Identify hooks, drop-risk passages, and a highlight clip from the transcript.

    USE WHEN: the user asks for retention analysis, engagement advice,
    what to cut, short-form clip ideas, or thumbnail hook suggestions.

    Args:
        transcript: the full transcript or text to analyse
        run_id: optional identifier for this pipeline run (used to group results)
    """
    from contentpipelinebot.subagents.retention_analyzer import retention_analyzer_agent

    result = await Runner.run(
        starting_agent=retention_analyzer_agent, input=transcript
    )
    analysis = result.final_output or "(no analysis produced)"

    if run_id:
        conn = _ensure_db()
        conn.execute(
            "INSERT INTO pipeline_results (run_id, stage, content) VALUES (?, ?, ?)",
            (run_id, "retention", analysis),
        )
        conn.commit()
        conn.close()

    safe = sanitize_for_telegram(analysis)
    return f"<b>Retention Analysis</b>\n\n{safe}"
