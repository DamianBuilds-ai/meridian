"""
Thin emit wrapper - call this at key moments in handlers/agents.

Wire-in to handlers.py:
    from shared.emit import emit_event

    # When a message arrives:
    await emit_event(bot_name, "message", preview=message.text)

    # When a tool fires (inside bot_application.py or agent tool wrappers):
    await emit_event(bot_name, "tool_call", tool="my_tool", preview=query)

    # When the agent sends a reply:
    await emit_event(bot_name, "response", preview=response_text)

The function is fire-and-forget - it never raises or blocks the caller.
Import it wherever you need it; it shares the module-level bus singleton.
"""

import asyncio
import logging

from shared.event_bus import bus

log = logging.getLogger("emit")


async def emit_event(
    bot: str,
    type: str,
    tool: str | None = None,
    preview: str | None = None,
) -> None:
    """
    Publish a bot event to the SSE bus. Non-blocking, never raises.

    Args:
        bot     - bot name, e.g. "assistant", "weather"
        type    - "message" | "tool_call" | "response"
        tool    - tool name when type=="tool_call", e.g. "get_weather"
        preview - first ~100 chars of content; will be truncated automatically
    """
    try:
        event = bus.make_event(bot=bot, type=type, tool=tool, preview=preview)
        await bus.publish(event)
    except Exception as e:
        # Never let emit failures surface to callers
        log.debug(f"emit_event failed silently: {e}")
