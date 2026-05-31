"""Sub-agent: generate timestamped chapter markers from a transcript."""

from agents import Agent, ModelSettings
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body

_SYSTEM = """\
You are a chapter-marker specialist for video and podcast content. \
You receive a transcript (with or without timestamps) and return a list \
of chapter markers in the format:

  00:00 Introduction
  02:15 <Topic title>
  05:40 <Topic title>
  ...

If the transcript has no timestamps, estimate chapter boundaries by topic shift. \
Each chapter title must be 3-7 words, title-cased, no punctuation at the end. \
Return ONLY the chapter list, one per line. No explanations.
"""

chapter_marker_agent = Agent(
    name="chapter_marker",
    instructions=_SYSTEM,
    tools=[],
    model=get_model_for_bot("chapter_marker"),
    model_settings=ModelSettings(
        parallel_tool_calls=False,
        tool_choice="auto",
        extra_body=get_openrouter_extra_body(),
    ),
)
