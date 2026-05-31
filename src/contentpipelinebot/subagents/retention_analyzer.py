"""Sub-agent: identify retention risk points and hooks in a transcript."""

from agents import Agent, ModelSettings
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body

_SYSTEM = """\
You are a content-retention analyst. You receive a transcript and identify:

1. HOOKS: up to 3 strong moments (quotes or paraphrases) that could serve as \
   attention hooks (thumbnail quote, intro hook, re-engagement moment).
2. DROP-RISK: up to 3 passages that risk audience drop-off \
   (slow pacing, jargon spikes, low-energy delivery, tangents). \
   Provide a one-sentence fix for each.
3. HIGHLIGHT CLIP: the single best 30-60 second passage for a short-form clip - \
   give the approximate position (e.g. "around minute 12") and a one-sentence \
   reason why.

Return the three sections clearly labelled. No bullet symbols - use plain numbered \
lists. No markdown.
"""

retention_analyzer_agent = Agent(
    name="retention_analyzer",
    instructions=_SYSTEM,
    tools=[],
    model=get_model_for_bot("retention_analyzer"),
    model_settings=ModelSettings(
        parallel_tool_calls=False,
        tool_choice="auto",
        extra_body=get_openrouter_extra_body(),
    ),
)
