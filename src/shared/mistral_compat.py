"""
Mistral OpenAI-compatible API wrapper.

Fixes two incompatibilities between Mistral's API and the OpenAI Agents SDK:

1. RESPONSE fix: Mistral returns type=None on tool calls instead of type='function'.
   The SDK ignores tool calls with type=None, causing empty responses.

2. REQUEST fix: Mistral requires tool_call_id to be exactly 9 alphanumeric chars (a-z, A-Z, 0-9).
   The OpenAI SDK generates 'call_XXX...' format IDs (24+ chars with underscores).
   If old session history from an OpenAI model is sent to Mistral, it rejects the IDs.
   This wrapper rewrites all tool_call_ids to 9-char alphanumeric before sending.
"""

import hashlib
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion


def _to_mistral_id(original_id: str) -> str:
    """Convert any tool_call_id to Mistral's 9-char alphanumeric format."""
    if not original_id:
        return "a" * 9
    # Already valid Mistral format
    if len(original_id) == 9 and original_id.isalnum():
        return original_id
    # Deterministic hash — same input always gives same output,
    # so assistant message IDs and tool response IDs stay matched
    h = hashlib.sha256(original_id.encode()).hexdigest()
    # Use first 9 chars of hex (0-9a-f) — valid alphanumeric
    return h[:9]


def _patch_request_messages(kwargs: dict):
    """Rewrite tool_call_ids in outgoing messages to Mistral-compatible format."""
    messages = kwargs.get("messages")
    if not messages:
        return

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        # Assistant messages with tool_calls
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict) and "id" in tc:
                    tc["id"] = _to_mistral_id(tc["id"])

        # Tool response messages
        if msg.get("role") == "tool" and "tool_call_id" in msg:
            msg["tool_call_id"] = _to_mistral_id(msg["tool_call_id"])


def _patch_tool_calls(response: ChatCompletion):
    """Set type='function' on any tool calls that have type=None."""
    if not response.choices:
        return
    for choice in response.choices:
        if choice.message and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                if tc.type is None:
                    tc.type = "function"


class MistralCompatClient(AsyncOpenAI):
    """AsyncOpenAI subclass that patches Mistral's tool call incompatibilities."""

    class _ChatCompletions:
        def __init__(self, original):
            self._original = original

        async def create(self, **kwargs):
            _patch_request_messages(kwargs)
            resp = await self._original.create(**kwargs)
            _patch_tool_calls(resp)
            return resp

    class _Chat:
        def __init__(self, original):
            self.completions = MistralCompatClient._ChatCompletions(original.completions)

    @property
    def chat(self):
        original_chat = super().chat
        return MistralCompatClient._Chat(original_chat)
