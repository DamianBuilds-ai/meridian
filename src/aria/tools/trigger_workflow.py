"""
trigger_workflow - POSTs a JSON payload to a configurable webhook URL.

The target URL is read from the ARIA_WEBHOOK_URL environment variable.
If the env var is not set, the tool returns a stub response so the bot
remains runnable without external dependencies.

TODO: Set ARIA_WEBHOOK_URL in your .env to the real automation webhook endpoint.
      Example platforms: n8n, Make, Zapier, custom FastAPI.
      See docs/adding-a-bot.md for wiring guidance.
"""

import json
import os

import httpx
from agents import function_tool
from shared.dates import local_now, to_iso

WEBHOOK_URL = os.getenv("ARIA_WEBHOOK_URL", "")

# How long to wait for the webhook to acknowledge (seconds)
WEBHOOK_TIMEOUT = float(os.getenv("ARIA_WEBHOOK_TIMEOUT", "8"))


@function_tool
async def trigger_workflow(
    workflow_name: str,
    payload_json: str = "{}",
) -> str:
    """Trigger an external automation workflow via a webhook POST.

    USE WHEN: The user asks to trigger, run, start, or fire an automation,
    workflow, or integration. For example: "trigger the invoice workflow",
    "run the weekly report", "kick off onboarding for client X".

    Args:
        workflow_name: Short identifier for the workflow to trigger. This is
                       included in the POST body so the receiving endpoint can
                       route to the right automation.
        payload_json:  Optional JSON string of extra key/value pairs to include
                       in the POST body. Defaults to '{}'.
    """
    # Parse optional extra payload; ignore invalid JSON gracefully
    try:
        extra = json.loads(payload_json) if payload_json.strip() else {}
    except json.JSONDecodeError:
        extra = {}

    body = {
        "workflow": workflow_name,
        "triggered_at": to_iso(local_now()),
        **extra,
    }

    # --- STUB path: no webhook URL configured ---
    if not WEBHOOK_URL:
        # TODO: Set ARIA_WEBHOOK_URL in your .env to enable real webhook calls.
        #       See docs/adding-a-bot.md for wiring guidance.
        return (
            f"<b>Workflow stub triggered</b>: <code>{workflow_name}</code>\n"
            f"<i>ARIA_WEBHOOK_URL is not set - this is a dry-run stub.\n"
            f"Payload that would be sent:</i>\n"
            f"<code>{json.dumps(body, indent=2)}</code>"
        )

    # --- Live path: fire the webhook ---
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            resp = await client.post(WEBHOOK_URL, json=body)
            resp.raise_for_status()
            status = resp.status_code
    except httpx.TimeoutException:
        return f"<i>Webhook timed out after {WEBHOOK_TIMEOUT}s for workflow <code>{workflow_name}</code>.</i>"
    except httpx.HTTPStatusError as exc:
        return (
            f"<i>Webhook returned HTTP {exc.response.status_code} for "
            f"<code>{workflow_name}</code>.</i>"
        )
    except Exception as exc:  # noqa: BLE001
        return f"<i>Webhook error for <code>{workflow_name}</code>: {exc}</i>"

    return (
        f"<b>Workflow triggered</b>: <code>{workflow_name}</code>\n"
        f"Status: HTTP {status}"
    )
