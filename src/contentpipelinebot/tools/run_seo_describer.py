"""Tool: invoke the seo_describer sub-agent on a transcript."""

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
async def run_seo_describer(transcript: str, run_id: str = "") -> str:
    """Generate an SEO-optimised title, description, and tags from the transcript.

    USE WHEN: the user asks for a YouTube description, video description,
    SEO copy, metadata, or tags for a piece of content.

    Args:
        transcript: the full transcript or text to describe
        run_id: optional identifier for this pipeline run (used to group results)
    """
    from contentpipelinebot.subagents.seo_describer import seo_describer_agent

    result = await Runner.run(starting_agent=seo_describer_agent, input=transcript)
    seo_copy = result.final_output or "(no SEO copy produced)"

    if run_id:
        conn = _ensure_db()
        conn.execute(
            "INSERT INTO pipeline_results (run_id, stage, content) VALUES (?, ?, ?)",
            (run_id, "seo", seo_copy),
        )
        conn.commit()
        conn.close()

    safe = sanitize_for_telegram(seo_copy)
    return f"<b>SEO Metadata</b>\n\n{safe}"
