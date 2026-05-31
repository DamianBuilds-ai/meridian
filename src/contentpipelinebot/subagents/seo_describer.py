"""Sub-agent: generate an SEO-optimised description from a transcript."""

from agents import Agent, ModelSettings
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body

_SYSTEM = """\
You are an SEO copywriter specialising in video and podcast descriptions. \
You receive a transcript and return:

  TITLE: <compelling title, under 70 characters>
  DESCRIPTION: <150-300 word description, keyword-rich, no fluff, present tense>
  TAGS: <10 comma-separated lowercase tags>

Rules:
- Title must hook the reader and include the main keyword.
- Description first sentence is the hook (under 20 words).
- Tags: specific first, broad last.
- Output ONLY the three labelled fields above. Nothing else.
"""

seo_describer_agent = Agent(
    name="seo_describer",
    instructions=_SYSTEM,
    tools=[],
    model=get_model_for_bot("seo_describer"),
    model_settings=ModelSettings(
        parallel_tool_calls=False,
        tool_choice="auto",
        extra_body=get_openrouter_extra_body(),
    ),
)
