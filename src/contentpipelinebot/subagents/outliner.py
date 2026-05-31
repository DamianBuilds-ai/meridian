"""Sub-agent: extract a structured outline from a transcript."""

from agents import Agent, ModelSettings
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body

_SYSTEM = """\
You are an outline specialist. You receive raw transcript text and return \
a clean hierarchical outline: main topics as numbered sections, \
key sub-points as lettered items beneath each section. \
No preamble. Return only the outline, using plain text (no markdown). \
Number each top-level section (1. 2. 3. ...) and letter sub-points (a. b. c. ...).
"""

outliner_agent = Agent(
    name="outliner",
    instructions=_SYSTEM,
    tools=[],
    model=get_model_for_bot("outliner"),
    model_settings=ModelSettings(
        parallel_tool_calls=False,
        tool_choice="auto",
        extra_body=get_openrouter_extra_body(),
    ),
)
