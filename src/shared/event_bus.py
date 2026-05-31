"""
In-memory event bus for SSE streaming of bot activity.

Wire-in to main.py:
    from shared.event_bus import bus
    app["event_bus"] = bus

Wire-in to handlers.py (or bot_application.py):
    from shared.emit import emit_event
    await emit_event("assistant", "message", preview=message.text[:100])
    await emit_event("assistant", "tool_call", tool="my_tool", preview=query[:100])
    await emit_event("assistant", "response", preview=response[:100])
"""

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("event_bus")

# Max events to buffer when no SSE clients are connected.
# Once the queue hits this limit, oldest events are dropped.
MAX_BUFFER = 50


class EventBus:
    """
    Simple pub/sub event bus backed by asyncio.Queue.

    Multiple SSE clients can subscribe simultaneously. Each gets its own
    queue so a slow client doesn't block others. Events are broadcast
    to all active subscriber queues.

    Events are NOT stored permanently - they exist only in live subscriber
    queues. If no clients are connected, events are dropped after MAX_BUFFER.
    """

    def __init__(self):
        # One asyncio.Queue per connected SSE client.
        # Key: arbitrary subscriber id (id(queue)), Value: asyncio.Queue
        self._subscribers: dict[int, asyncio.Queue] = {}

        # Small ring buffer for late-joining clients (last N events only)
        self._buffer: list[dict] = []

    def subscribe(self) -> asyncio.Queue:
        """
        Register a new SSE client. Returns a queue to read events from.
        Replays the recent buffer so new clients see the last few events.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_BUFFER)
        self._subscribers[id(q)] = q

        # Replay buffer for late joiners (best-effort, non-blocking)
        for event in self._buffer:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                break  # Buffer full - skip oldest replays

        log.debug(f"SSE subscriber added. Total: {len(self._subscribers)}")
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Deregister an SSE client when it disconnects."""
        key = id(q)
        self._subscribers.pop(key, None)
        log.debug(f"SSE subscriber removed. Total: {len(self._subscribers)}")

    async def publish(self, event: dict):
        """
        Broadcast an event to all active SSE subscribers.

        Also maintains the small replay buffer so clients joining mid-session
        can see recent activity. Non-blocking - slow/full queues are skipped.
        """
        # Update ring buffer (keep last MAX_BUFFER/5 events)
        self._buffer.append(event)
        if len(self._buffer) > MAX_BUFFER // 5:
            self._buffer.pop(0)

        if not self._subscribers:
            return  # Nobody listening - drop the event

        dead = []
        for key, q in self._subscribers.items():
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Client is too slow to consume - drop this event for them
                log.debug(f"SSE subscriber {key} queue full, dropping event")
            except Exception as e:
                log.warning(f"SSE subscriber {key} error: {e}")
                dead.append(key)

        # Clean up any broken subscribers
        for key in dead:
            self._subscribers.pop(key, None)

    def make_event(
        self,
        bot: str,
        type: str,
        tool: str | None = None,
        preview: str | None = None,
    ) -> dict:
        """
        Build a structured event dict.

        Fields:
            bot      - which bot triggered this (e.g. "assistant")
            type     - "message" | "tool_call" | "response"
            tool     - tool name if type is "tool_call" (e.g. "search_contacts")
            preview  - first ~100 chars of content for display
            timestamp - ISO 8601 UTC
        """
        return {
            "bot": bot,
            "type": type,
            "tool": tool,
            "preview": (preview or "")[:100],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton - import this everywhere
bus = EventBus()
