"""Tool: load a transcript from a local file path or return inline text as-is."""

import os
from agents import function_tool

# Directory where sample transcripts can be dropped.
# Set CONTENT_PIPELINE_TRANSCRIPT_DIR in .env to override.
_TRANSCRIPT_DIR = os.getenv("CONTENT_PIPELINE_TRANSCRIPT_DIR", "/tmp/transcripts")

# Maximum characters read from a transcript file to avoid token overload.
_MAX_CHARS = 20_000


@function_tool
async def load_transcript(source: str) -> str:
    """Load a transcript for processing.

    USE WHEN: the user provides a filename or says the transcript is in a file.
    For inline text, the hub agent should pass the text directly to a specialist tool.

    Accepts two forms:
    - A bare filename (e.g. "episode42.txt") - resolved against CONTENT_PIPELINE_TRANSCRIPT_DIR
    - An absolute file path (e.g. "/tmp/transcripts/episode42.txt")

    Returns the first 20,000 characters of the file.

    Args:
        source: filename or absolute path of the transcript file
    """
    if os.path.isabs(source):
        path = source
    else:
        path = os.path.join(_TRANSCRIPT_DIR, source)

    if not os.path.exists(path):
        # Return a stub / illustrative response for demo purposes.
        # TODO: replace with your real transcript storage or ingestion backend.
        # See docs/adding-a-bot.md for integration guidance.
        sample = (
            "[STUB] No file found at the requested path. "
            "This is an illustrative sample transcript.\n\n"
            "Welcome to the show. Today we are talking about building AI pipelines. "
            "In the first segment we cover the basics of agent-based architectures. "
            "Moving on, we explore tool use and how sub-agents can be chained together. "
            "Finally, we discuss deployment patterns and production hardening. "
            "Thanks for listening."
        )
        return sample

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(_MAX_CHARS)
        return content
    except OSError as exc:
        return f"[ERROR] Could not read file: {exc}"
