"""
Bot Gateway - Entry point.

Supports three modes:
- Single-bot mode: Set BOT_NAME env var to run one isolated bot per container.
- Gateway mode: Set GATEWAY_MODE=true to run shared endpoints (hub, models, chat proxy).
- Legacy mode: No env vars set - loads all bots in one process (backwards compatible).

To add a new bot:
1. Create src/{bot_name}/agent.py exporting `{bot_name}_agent`.
2. Register it in agents_registry.py (ALL_AGENTS).
3. Add its token field to ALL_BOT_TOKENS below.
4. Add REQUIRED_CREDENTIALS for it in config.py.
"""

import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

import json
import time
import re
import os

from config import settings, check_bot_credentials

# --- Langfuse Observability ---
# MUST run before any agent/bot imports so MistralCompatClient inherits the patched AsyncOpenAI
if settings.langfuse_public_key:
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url
    try:
        from langfuse.openai import openai as langfuse_openai
        import openai
        openai.AsyncOpenAI = langfuse_openai.AsyncOpenAI
        openai.OpenAI = langfuse_openai.OpenAI
    except Exception:
        pass  # langfuse openai wrapper not available

from handlers import register_handlers
from agents import Runner
from agents_registry import get_agent_for_bot
from session import get_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gateway")

# --- Mode detection ---
BOT_NAME = os.environ.get("BOT_NAME", "").strip().lower()
GATEWAY_MODE = os.environ.get("GATEWAY_MODE", "").strip().lower() == "true"

# All known bots and their token settings field names.
# Add an entry here for each bot you register in agents_registry.py.
ALL_BOT_TOKENS = {
    "assistant": "telegram_bot_token_assistant",
    "weather": "telegram_bot_token_weather",
    "notes": "telegram_bot_token_notes",
}

# Host ports for reference/deploy scripts (nginx routes to these).
# Assign a unique port for each bot container.
BOT_HOST_PORTS = {
    "assistant": 8101,
    "weather": 8102,
    "notes": 8103,
}

# Docker internal URLs (container-name:internal-port, used by gateway mode to proxy to bot containers)
BOT_DOCKER_URLS = {
    name: f"http://bot-{name}:8090" for name in BOT_HOST_PORTS
}


def create_bots() -> dict[str, Bot]:
    """Create Bot instances. In single-bot mode, only creates the named bot."""
    bots = {}

    if BOT_NAME:
        # Single-bot mode - load only the named bot
        token_field = ALL_BOT_TOKENS.get(BOT_NAME)
        if not token_field:
            log.error(f"Unknown bot: {BOT_NAME}")
            return bots
        token = getattr(settings, token_field, "")
        if not token:
            log.error(f"No token configured for {BOT_NAME}")
            return bots
        missing = check_bot_credentials(BOT_NAME)
        if missing:
            log.error(f"Missing credentials for {BOT_NAME}: {missing}")
            return bots
        bots[BOT_NAME] = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        log.info(f"[single-bot] {BOT_NAME}: credentials OK")
        return bots

    # Legacy mode - load all bots
    for name, token_field in ALL_BOT_TOKENS.items():
        token = getattr(settings, token_field, "")
        if not token:
            continue
        missing = check_bot_credentials(name)
        if missing:
            log.warning(f"Skipping {name}: missing credentials {missing}")
            continue
        bots[name] = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        log.info(f"Bot {name}: credentials OK")

    return bots


async def on_startup(app: web.Application):
    """Register webhooks with Telegram on startup.

    `allowed_updates` is set explicitly to include `callback_query` so
    inline-keyboard taps from shared/telegram_buttons.py route through
    `@dp.callback_query()` in handlers.py. Without this list, Telegram's
    default still includes callback_query - but being explicit prevents
    silent breakage if anyone later passes a narrower subset.
    Includes: message (text/voice/photo), callback_query (inline buttons),
    edited_message (for future edit-detection), inline_query (forwards-compat).
    """
    bots: dict[str, Bot] = app["bots"]
    allowed_updates = [
        "message",
        "edited_message",
        "callback_query",
        "inline_query",
    ]

    for name, bot in bots.items():
        webhook_url = f"{settings.webhook_base_url}/{name}"
        await bot.set_webhook(
            webhook_url,
            drop_pending_updates=True,
            allowed_updates=allowed_updates,
        )
        me = await bot.get_me()
        log.info(f"Bot @{me.username} ({name}) webhook -> {webhook_url}")


async def on_shutdown(app: web.Application):
    """Cleanup on shutdown."""
    bots: dict[str, Bot] = app["bots"]
    for name, bot in bots.items():
        await bot.delete_webhook()
        await bot.session.close()
        log.info(f"Bot {name} webhook removed, session closed.")


def main():
    if GATEWAY_MODE:
        return run_gateway()
    return run_bot()


def run_bot():
    """Run in bot mode - either single-bot or legacy all-bots."""
    mode = f"single-bot ({BOT_NAME})" if BOT_NAME else "legacy (all bots)"
    log.info(f"Starting in {mode} mode")

    dp = Dispatcher()
    register_handlers(dp)

    bots = create_bots()
    if not bots:
        log.error("No bot tokens configured. Set TELEGRAM_BOT_TOKEN_* in .env")
        return

    app = web.Application()
    app["bots"] = bots

    bot_names = list(bots.keys())

    # Health check
    @web.middleware
    async def health_middleware(request, handler):
        if request.path == "/health":
            return web.json_response({
                "status": "ok",
                "mode": "single" if BOT_NAME else "legacy",
                "bot": BOT_NAME or None,
                "bots": len(bots),
                "bot_names": bot_names,
            })
        return await handler(request)
    app.middlewares.append(health_middleware)

    # SSE live feed (per-bot in single mode, all bots in legacy)
    from shared.sse import handle_sse
    app.router.add_get("/live", handle_sse)

    # Static files only in legacy/gateway mode (not per-bot containers)
    if not BOT_NAME:
        import pathlib
        static_dir = pathlib.Path(__file__).parent / "static"
        if static_dir.exists():
            app.router.add_static("/static/", static_dir, show_index=True)
            async def hub_redirect(request):
                return web.FileResponse(static_dir / "hub.html")
            app.router.add_get("/hub", hub_redirect)

            ui_dir = static_dir / "ui"
            if ui_dir.exists():
                async def ui_index(request):
                    return web.FileResponse(ui_dir / "index.html")
                app.router.add_get("/ui", ui_index)
                app.router.add_get("/ui/", ui_index)
                app.router.add_get("/ui/{path:.*}", ui_index)
                app.router.add_static("/ui/assets/", ui_dir / "assets")
                log.info("Registered route: /ui (React Flow Meridian UI)")
            log.info("Registered route: /hub + /static/ + /ui (dashboards)")

    # Register webhook handlers
    for name, bot in bots.items():
        handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        handler.register(app, path=f"/webhook/bots/{name}")
        log.info(f"Registered route: /webhook/bots/{name}")

    # OpenAI-compatible chat endpoint (works for single-bot too)
    async def handle_chat_completions(request: web.Request) -> web.Response:
        """OpenAI-compatible /v1/chat/completions endpoint."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        messages = body.get("messages", [])
        model_field = body.get("model", BOT_NAME or "assistant")
        bot_name = model_field.split("/")[-1].lower().replace("-test", "")

        # In single-bot mode, always use this bot regardless of model field
        if BOT_NAME:
            bot_name = BOT_NAME

        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        if not user_msg:
            return web.json_response({"error": "No user message found"}, status=400)

        agent = get_agent_for_bot(bot_name)
        if not agent:
            return web.json_response({"error": f"Bot '{bot_name}' not found"}, status=404)

        log.info(f"[chat/{bot_name}] {user_msg[:80]}")
        session = get_session(bot_name, 0)

        try:
            result = await Runner.run(agent, input=user_msg, session=session)
            response_text = result.final_output or "Done."

            tool_output = None
            for item in result.new_items:
                item_type = getattr(item, 'type', '')
                if item_type == 'tool_call_output_item':
                    output = getattr(item, 'output', '')
                    if output and len(output) > 100:
                        tool_output = output

            if tool_output and len(tool_output) > len(response_text):
                response_text = tool_output

        except Exception as e:
            log.exception(f"[chat/{bot_name}] Error")
            response_text = f"Error: {type(e).__name__}: {str(e)[:200]}"

        text = response_text
        text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)
        text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.DOTALL)
        text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)
        text = re.sub(r"</?[a-z][^>]*>", "", text)

        return web.json_response({
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_field,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    async def handle_models(request: web.Request) -> web.Response:
        """OpenAI-compatible /v1/models endpoint."""
        if BOT_NAME:
            data = [{"id": BOT_NAME, "object": "model", "owned_by": "meridian"}]
        else:
            data = [{"id": n, "object": "model", "owned_by": "meridian"} for n in bots]
        return web.json_response({"object": "list", "data": data})

    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_get("/v1/models", handle_models)
    log.info("Registered: /v1/chat/completions + /v1/models")

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    log.info(f"Starting with {len(bots)} bot(s) on port 8090")
    web.run_app(app, host="0.0.0.0", port=8090)


def run_gateway():
    """Run in gateway mode - shared endpoints only, proxies to bot containers."""
    import httpx

    log.info("Starting in GATEWAY mode (shared endpoints, no bots)")
    app = web.Application()

    # Health - aggregates from all bot containers via Docker network
    @web.middleware
    async def health_middleware(request, handler):
        if request.path == "/health":
            statuses = {}
            async with httpx.AsyncClient(timeout=3) as client:
                for name, url in BOT_DOCKER_URLS.items():
                    try:
                        resp = await client.get(f"{url}/health")
                        statuses[name] = resp.json() if resp.status_code == 200 else "error"
                    except Exception:
                        statuses[name] = "unreachable"
            healthy = sum(1 for v in statuses.values() if isinstance(v, dict))
            return web.json_response({
                "status": "ok" if healthy > 0 else "degraded",
                "mode": "gateway",
                "bots_healthy": healthy,
                "bots_total": len(BOT_DOCKER_URLS),
                "details": statuses,
            })
        return await handler(request)
    app.middlewares.append(health_middleware)

    # Static files (hub, UI)
    import pathlib
    static_dir = pathlib.Path(__file__).parent / "static"
    if static_dir.exists():
        app.router.add_static("/static/", static_dir, show_index=True)
        async def hub_redirect(request):
            return web.FileResponse(static_dir / "hub.html")
        app.router.add_get("/hub", hub_redirect)

        ui_dir = static_dir / "ui"
        if ui_dir.exists():
            async def ui_index(request):
                return web.FileResponse(ui_dir / "index.html")
            app.router.add_get("/ui", ui_index)
            app.router.add_get("/ui/", ui_index)
            app.router.add_get("/ui/{path:.*}", ui_index)
            app.router.add_static("/ui/assets/", ui_dir / "assets")

    # SSE aggregator - fans out to all bot /live endpoints
    from shared.sse import handle_sse
    app.router.add_get("/live", handle_sse)

    # Proxy /v1/chat/completions to the right bot container
    async def handle_chat_completions(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        model_field = body.get("model", "assistant")
        bot_name = model_field.split("/")[-1].lower().replace("-test", "")
        bot_url = BOT_DOCKER_URLS.get(bot_name)

        if not bot_url:
            return web.json_response({"error": f"Unknown bot: {bot_name}"}, status=404)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{bot_url}/v1/chat/completions",
                    json=body,
                )
                return web.json_response(resp.json(), status=resp.status_code)
        except Exception as e:
            return web.json_response({"error": f"Bot {bot_name} unreachable: {e}"}, status=502)

    async def handle_models(request: web.Request) -> web.Response:
        data = [{"id": n, "object": "model", "owned_by": "meridian"} for n in BOT_DOCKER_URLS]
        return web.json_response({"object": "list", "data": data})

    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_get("/v1/models", handle_models)

    log.info(f"Gateway ready - proxying to {len(BOT_DOCKER_URLS)} bot containers")
    web.run_app(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
