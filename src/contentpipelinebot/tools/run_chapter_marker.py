"""Tool: invoke the chapter_marker sub-agent on a transcript."""

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
async def run_chapter_marker(transcript: str, run_id: str = "") -> str:
    """Generate timestamped chapter markers from the provided transcript.

    USE WHEN: the user asks for chapters, timestamps, chapter markers,
    or a YouTube description with timestamps.

    Args:
        transcript: the full transcript or text to chapter-mark
        run_id: optional identifier for this pipeline run (used to group results)
    """
    from contentpipelinebot.subagents.chapter_marker import chapter_marker_agent

    result = await Runner.run(starting_agent=chapter_marker_agent, input=transcript)
    chapters = result.final_output or "(no chapters produced)"

    if run_id:
        conn = _ensure_db()
        conn.execute(
            "INSERT INTO pipeline_results (run_id, stage, content) VALUES (?, ?, ?)",
            (run_id, "chapters", chapters),
        )
        conn.commit()
        conn.close()

    safe = sanitize_for_telegram(chapters)
    return f"<b>Chapter Markers</b>\n\n<code>{safe}</code>"
