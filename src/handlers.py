"""
Message handlers - routes Telegram messages to the right Agent.

This is the bridge between aiogram (Telegram) and OpenAI Agents SDK.
"""

import json
import logging
from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery
from agents import Runner

from config import settings
from agents_registry import get_agent_for_bot
from session import get_session
from shared.telegram_format import sanitize_for_telegram
from shared.emit import emit_event
from shared.ping_state import get_ping, get_pending_pings, ack_ping
from shared.telegram_buttons import parse_callback_data, edit_message_after_action

log = logging.getLogger("handlers")

# Map bot tokens to bot names (built at import time)
TOKEN_TO_NAME: dict[str, str] = {}

# Single-bot mode shortcut
import os
_BOT_NAME = os.environ.get("BOT_NAME", "").strip().lower()

# All token fields mapped to bot names.
# Add an entry here for each bot you register in agents_registry.py.
_TOKEN_FIELDS = {
    "telegram_bot_token_assistant": "assistant",
    "telegram_bot_token_weather": "weather",
    "telegram_bot_token_notes": "notes",
}


def _build_token_map():
    for field, name in _TOKEN_FIELDS.items():
        if _BOT_NAME and name != _BOT_NAME:
            continue  # Skip other bots in single-bot mode
        token = getattr(settings, field, "")
        if token:
            TOKEN_TO_NAME[token] = name


_build_token_map()


def _is_allowed(user_id: int) -> bool:
    """Check if user is in the allowed list."""
    if not settings.allowed_user_ids:
        return True  # No allowlist = allow all (dev mode)
    return user_id in settings.allowed_user_ids


async def _run_agent(bot_name: str, user_id: int, text: str) -> str:
    """Run the agent via Burr state machine (tracking + time-travel + Langfuse).

    Tracing strategy (transitional - 2026-05-17):
    - PRIMARY: native Langfuse v4 propagate_attributes() sets user_id, tags,
      session_id BEFORE the OpenAI generation is created. Eliminates the
      concurrent-bot race condition (each task has its own contextvars).
    - SAFETY NET: post-hoc _tag_window_traces sweeper still runs. It self-skips
      already-tagged traces (`if t.get("tags"): continue`), so no conflict.
      Will be removed once native path is verified on a canary bot.
    """
    from bot_application import handle_message
    import time as _time

    before = _time.time()

    # Per-call upstream provider + model tracking.
    try:
        from config import settings as _settings, BOT_MODEL_MAP as _BMM
        _model_id = _settings.openrouter_model_id if _BMM.get(bot_name) == "openrouter" else "non-openrouter"
        _provider_pref = ",".join(_settings.openrouter_provider_order)
    except Exception:
        _model_id = "unknown"
        _provider_pref = "unknown"

    # Native per-bot tracing via Langfuse v4 propagate_attributes (race-safe)
    try:
        from langfuse import propagate_attributes
        with propagate_attributes(
            user_id=bot_name,                       # populates Langfuse Users view
            tags=[bot_name],                        # what the metrics endpoint groups by
            session_id=f"{bot_name}_{user_id}",     # groups conversation traces
            metadata={
                "bot": bot_name,
                "telegram_user_id": str(user_id),
                "model_id": _model_id,
                "provider_preference": _provider_pref,
            },
        ):
            result = await handle_message(bot_name, user_id, text)
    except ImportError:
        # propagate_attributes only exists on Langfuse v4+; fall back to plain call
        result = await handle_message(bot_name, user_id, text)

    after = _time.time()

    # SAFETY NET: post-hoc tag sweeper (skips traces already tagged by native path)
    try:
        import threading
        threading.Thread(
            target=_tag_window_traces,
            args=(bot_name, user_id, before, after),
            daemon=True,
        ).start()
    except Exception:
        pass

    return result


def _tag_window_traces(bot_name: str, user_id: int, before: float, after: float):
    """Tag all recent untagged Langfuse traces with this bot's name."""
    import time
    time.sleep(5)  # Wait for Langfuse to index

    try:
        import httpx
        import base64
        from config import settings

        if not settings.langfuse_public_key:
            return

        auth = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

        with httpx.Client(timeout=5) as client:
            resp = client.get(
                f"{settings.langfuse_base_url}/api/public/traces",
                params={"limit": 20},
                headers=headers,
            )
            if resp.status_code != 200:
                return

            traces = resp.json().get("data", [])
            batch = []
            for t in traces:
                if t.get("tags"):
                    continue
                batch.append({
                    "id": f"tag-{t['id'][:12]}",
                    "type": "trace-create",
                    "timestamp": t.get("timestamp", "2026-01-01T00:00:00Z"),
                    "body": {
                        "id": t["id"],
                        "name": f"{bot_name}_run",
                        "tags": [bot_name],
                        "metadata": {"bot": bot_name, "user_id": user_id},
                        "sessionId": f"{bot_name}_{user_id}",
                    },
                })

            if batch:
                client.post(
                    f"{settings.langfuse_base_url}/api/public/ingestion",
                    headers=headers,
                    json={"batch": batch},
                )
                log.info(f"Tagged {len(batch)} traces as '{bot_name}'")
    except Exception as e:
        log.warning(f"Trace tagging: {e}")



def register_handlers(dp: Dispatcher):
    """Register all message handlers on the dispatcher."""

    @dp.message(F.text)
    async def handle_text(message: Message):
        if not _is_allowed(message.from_user.id):
            return

        bot_name = TOKEN_TO_NAME.get(message.bot.token)
        if not bot_name:
            log.warning(f"Unknown bot token: {message.bot.token[:10]}...")
            return

        log.info(f"[{bot_name}] {message.from_user.id}: {message.text[:80]}")
        emit_event(bot_name, "message", preview=message.text[:120])

        # If there are pending pings in this chat (last 60 min), prepend
        # them to the user's text so the agent can route fuzzy replies like
        # "todo 1,3" or "add but tag Home" to the right ping context.
        # Most messages have zero pending pings - the lookup is one indexed
        # SQLite SELECT and adds <1ms when empty.
        user_text = message.text
        try:
            pending = await get_pending_pings(message.chat.id, max_count=3)
        except Exception as e:
            log.warning(f"[{bot_name}] get_pending_pings failed: {e}")
            pending = []
        if pending:
            lines = ["[PENDING PINGS (last 60 min):"]
            for p in pending:
                ctx = p.get("context") or {}
                kind = ctx.get("kind", "unknown")
                items = ctx.get("items") or []
                if items:
                    summary = ", ".join(
                        str(it.get("title") or it.get("subject") or it.get("sender") or it)
                        for it in items[:5]
                    )
                    lines.append(
                        f"  - ping_id={p['ping_id']} kind={kind} items=[{summary}]"
                    )
                else:
                    lines.append(f"  - ping_id={p['ping_id']} kind={kind}")
            lines.append("")
            lines.append(
                "If the user's message references any of these, route to that "
                "ping context. Otherwise ignore the pings and treat the message "
                "as a fresh request."
            )
            lines.append("")
            lines.append(f"User message: {message.text}]")
            user_text = "\n".join(lines)

        try:
            response = await _run_agent(bot_name, message.from_user.id, user_text)
            if not response or not response.strip():
                log.error(f"[{bot_name}] empty response from agent; sending fallback")
                response = "Got it."
            emit_event(bot_name, "response", preview=response[:120])
            for chunk in _split_message(sanitize_for_telegram(response)):
                if not chunk.strip():
                    continue
                await message.answer(chunk)
        except Exception as e:
            log.exception(f"[{bot_name}] Error handling message")
            await message.answer(f"Something went wrong: {type(e).__name__}: {str(e)[:200]}")

    @dp.message(F.voice)
    async def handle_voice(message: Message):
        """Transcribe voice with Groq Whisper, then process as text."""
        if not _is_allowed(message.from_user.id):
            return

        bot_name = TOKEN_TO_NAME.get(message.bot.token)
        if not bot_name:
            return

        await message.answer("Transcribing...")

        try:
            file = await message.bot.get_file(message.voice.file_id)
            voice_bytes = await message.bot.download_file(file.file_path)
            transcript = await _transcribe_voice(voice_bytes.read())
            if not transcript:
                await message.answer("Couldn't transcribe that. Try again?")
                return

            log.info(f"[{bot_name}] {message.from_user.id} (voice): {transcript[:80]}")
            response = await _run_agent(bot_name, message.from_user.id, transcript)
            for chunk in _split_message(sanitize_for_telegram(response)):
                await message.answer(chunk)
        except Exception as e:
            log.exception(f"[{bot_name}] Voice handling error")
            await message.answer(f"Voice error: {type(e).__name__}: {str(e)[:200]}")

    @dp.message(F.photo)
    async def handle_photo(message: Message):
        """OCR the photo and pass result to the agent."""
        if not _is_allowed(message.from_user.id):
            return

        bot_name = TOKEN_TO_NAME.get(message.bot.token)
        if not bot_name:
            return

        try:
            photo = message.photo[-1]
            file = await message.bot.get_file(photo.file_id)
            photo_bytes_io = await message.bot.download_file(file.file_path)
            photo_bytes = photo_bytes_io.read()
            caption = message.caption or ""

            ocr_text = await _ocr_photo(photo_bytes)
            combined = f"{caption}\n\n[Photo OCR result]:\n{ocr_text}" if ocr_text else caption

            if not combined.strip():
                await message.answer("Couldn't read anything from that photo.")
                return

            log.info(f"[{bot_name}] {message.from_user.id} (photo): {combined[:80]}")
            response = await _run_agent(bot_name, message.from_user.id, combined)
            for chunk in _split_message(sanitize_for_telegram(response)):
                await message.answer(chunk)
        except Exception as e:
            log.exception(f"[{bot_name}] Photo handling error")
            await message.answer(f"Photo error: {type(e).__name__}: {str(e)[:200]}")

    @dp.callback_query()
    async def handle_callback_query(cb: CallbackQuery):
        """Generic callback router - parses ping_id:action and dispatches.

        Verb handlers (commit_bot_task, ack_email, snooze, etc.) are not
        wired in yet - they ship per-feature in subsequent extensions. For now
        this handler:
          1. Answers the callback within 30s (Telegram timeout)
          2. Resolves the ping from SQLite
          3. Edits the message to either "expired" or "TODO: verb {action}"
          4. Marks the ping acked so it falls out of pending lookups
        """
        if not _is_allowed(cb.from_user.id):
            await cb.answer("Not authorised.")
            return

        bot_name = TOKEN_TO_NAME.get(cb.message.bot.token) if cb.message else None
        if not bot_name:
            await cb.answer("Unknown bot.")
            return

        # 1. Answer immediately to kill the loading spinner (30s Telegram cap)
        await cb.answer("Working...")

        # 2. Parse the callback data
        ping_id, action = parse_callback_data(cb.data or "")
        if not ping_id:
            log.warning(f"[{bot_name}] malformed callback_data: {cb.data!r}")
            try:
                await edit_message_after_action(
                    cb.message.bot, cb.message.chat.id, cb.message.message_id,
                    (cb.message.text or "") + "\n\n<i>Stale button - ignored.</i>",
                )
            except Exception:
                pass
            return

        # 3. Look up the ping
        try:
            ping = await get_ping(ping_id)
        except Exception as e:
            log.exception(f"[{bot_name}] get_ping failed: {e}")
            ping = None

        if not ping or ping.get("status") != "pending":
            # Most common cause: bot restarted, ping older than TTL, or
            # already-acked from a prior tap. Edit the message to remove
            # buttons so the user can't tap again.
            log.info(f"[{bot_name}] callback for expired/missing ping {ping_id}")
            try:
                await edit_message_after_action(
                    cb.message.bot, cb.message.chat.id, cb.message.message_id,
                    (cb.message.text or "") + "\n\n<i>Ping expired - reply with text instead.</i>",
                )
            except Exception:
                pass
            return

        # 4. Dispatch by ping kind. Callback-data shape: "{ping_id}:{verb}:{row_id}"
        # parse_callback_data returned (ping_id, action) where action is "{verb}:{row_id}"
        # for review pings, or just "{verb}" for simpler pings.
        kind = (ping.get("context") or {}).get("kind") or ""
        log.info(
            f"[{bot_name}] callback ping_id={ping_id} action={action} kind={kind}"
        )
        emit_event(
            bot_name, "callback_query",
            preview=f"ping={ping_id} action={action}",
        )

        result_text = ""
        try:
            # No verb dispatch registered yet - extend this block per-bot as needed
            result_text = f"TODO: implement verb {action} for kind={kind}"
        except Exception as e:
            log.exception(f"[{bot_name}] verb dispatch failed: {e}")
            result_text = f"Action failed: {type(e).__name__}: {str(e)[:160]}"

        # Mark acked so the ping falls out of pending lookups
        try:
            await ack_ping(ping_id, result={"action": action, "result": result_text[:200], "via": "callback"})
        except Exception as e:
            log.warning(f"[{bot_name}] ack_ping failed: {e}")

        # Edit the message to show the action taken
        try:
            new_text = (cb.message.text or "") + f"\n\n[done] {result_text}"
            await edit_message_after_action(
                cb.message.bot, cb.message.chat.id, cb.message.message_id, new_text,
            )
        except Exception as e:
            log.warning(f"[{bot_name}] edit_message_after_action failed: {e}")

    # If a bot defines a custom aiogram Router (for slash-command fast-path routing
    # or any other per-bot handler extension), register it here.
    # Example:
    #   try:
    #       from mybot.handler import mybot_router
    #       dp.include_router(mybot_router)
    #   except Exception as e:
    #       log.warning(f"Could not register mybot_router: {e}")



async def _transcribe_voice(audio_bytes: bytes) -> str | None:
    """Transcribe audio using Groq Whisper API."""
    import httpx

    if not settings.groq_api_key:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            files={"file": ("voice.ogg", audio_bytes, "audio/ogg")},
            data={"model": "whisper-large-v3-turbo", "language": "en"},
        )
        resp.raise_for_status()
        return resp.json().get("text")


async def _ocr_photo(image_bytes: bytes, prompt: str | None = None) -> str | None:
    """OCR image using Gemini Flash via OpenAI-compatible endpoint."""
    import base64
    import httpx

    if not settings.gemini_api_key:
        return None

    if prompt is None:
        prompt = "Extract all text from this image. Return only the extracted text, nothing else."

    b64 = base64.b64encode(image_bytes).decode()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": f"Bearer {settings.gemini_api_key}"},
            json={
                "model": "gemini-2.0-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split a message into chunks that fit Telegram's limit."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
