"""
SSE (Server-Sent Events) handler for the /live endpoint.

Wire-in to main.py - add these two lines before `app.on_startup.append(...)`:

    from shared.sse import handle_sse
    app.router.add_get("/live", handle_sse)

Then open a browser or curl to see the stream:
    curl -N http://localhost:8090/live

Events arrive as:
    data: {"bot":"assistant","type":"tool_call","tool":"my_tool","preview":"Looking up...","timestamp":"..."}

Heartbeat (every 15s, keeps proxies/browsers from closing idle connections):
    : heartbeat

Connection ends when the client disconnects.
"""

import asyncio
import json
import logging

from aiohttp import web

from shared.event_bus import bus

log = logging.getLogger("sse")

HEARTBEAT_INTERVAL = 15  # seconds


async def handle_sse(request: web.Request) -> web.StreamResponse:
    """
    GET /live - stream bot events as Server-Sent Events.

    Each event is formatted as:
        data: {json}\n\n

    Heartbeats are sent as SSE comments (ignored by EventSource clients):
        : heartbeat\n\n
    """
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Allow cross-origin access for dashboard UIs
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    q = bus.subscribe()
    log.info(f"SSE client connected from {request.remote}")

    try:
        while True:
            # Wait for next event, but wake up for heartbeats
            try:
                event = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_INTERVAL)
                payload = f"data: {json.dumps(event)}\n\n"
                await response.write(payload.encode())
            except asyncio.TimeoutError:
                # No event within heartbeat window - send a keep-alive comment
                await response.write(b": heartbeat\n\n")
            except asyncio.CancelledError:
                break

    except (ConnectionResetError, asyncio.CancelledError):
        pass  # Client disconnected cleanly
    except Exception as e:
        log.warning(f"SSE stream error: {e}")
    finally:
        bus.unsubscribe(q)
        log.info(f"SSE client disconnected from {request.remote}")

    return response
