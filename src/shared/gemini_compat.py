"""
Gemini OpenAI-compatible API wrapper.

Google exposes an OpenAI-compatible endpoint at
https://generativelanguage.googleapis.com/v1beta/openai/. Most things just
work, but we set thinking OFF explicitly on every call (non-reasoning tasks do not
need thinking mode, ~5x cheaper).

Thinking is controlled via extra_body.thinking_config.thinking_budget = 0.
See: https://ai.google.dev/gemini-api/docs/thinking
"""

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion


def _patch_tool_calls(response: ChatCompletion):
    """Set type='function' on any tool calls that have type=None.
    Mirror of mistral_compat - same precaution in case Gemini's OpenAI-compat
    layer ever returns type=None on tool calls."""
    if not response.choices:
        return
    for choice in response.choices:
        if choice.message and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                if tc.type is None:
                    tc.type = "function"


class GeminiCompatClient(AsyncOpenAI):
    """AsyncOpenAI subclass for Google Gemini's OpenAI-compatible endpoint."""

    def __init__(self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/", **kwargs):
        super().__init__(base_url=base_url, api_key=api_key, **kwargs)

    class _ChatCompletions:
        def __init__(self, original):
            self._original = original

        async def create(self, **kwargs):
            # NOTE: Gemini's OpenAI-compat endpoint does NOT accept
            # `thinking_config` in extra_body (returns 400 "Unknown name").
            # 2.5 Flash is non-thinking by default in tool-calling flows,
            # so we pass through as-is. If we ever need to force a budget,
            # use the native v1beta endpoint via google.generativeai instead.
            resp = await self._original.create(**kwargs)
            _patch_tool_calls(resp)
            return resp

    class _Chat:
        def __init__(self, original):
            self.completions = GeminiCompatClient._ChatCompletions(original.completions)

    @property
    def chat(self):
        return GeminiCompatClient._Chat(super().chat)
