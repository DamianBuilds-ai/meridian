"""Inline-keyboard helpers for aiogram-based bots.

This is the aiogram-side companion to ping_state.py. Per-bot keyboard
builders (e.g. build_email_digest_keyboard, build_review_task_keyboard)
live in the bot's own module; this file provides the generic primitives.

Callback-data convention:
    "{ping_id}:{action}"

The ping_id (8 URL-safe chars) is the SQLite primary key into pings;
{action} is the verb the callback handler dispatches on (e.g.
"commit_all", "snooze_1h", "ack_email"). Verb handlers are added per-feature
in subsequent work - this module is infrastructure only.

Why ping_id-first: every callback resolves a ping_id lookup BEFORE
dispatching the verb. Keeping ping_id at the front lets the parser fail
fast on malformed data and lets the dispatcher pre-fetch ping state once.

Total bytes used: 8 (ping_id) + 1 (colon) + up to 30 (verb) = 39, well
under Telegram's 64-byte callback_data cap.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_inline_keyboard(
    buttons: list[tuple[str, str]],
) -> InlineKeyboardMarkup:
    """Build an aiogram InlineKeyboardMarkup from (label, callback_data) tuples.

    Each tuple becomes its own row (single-column layout). For multi-column
    layouts, build the markup directly with aiogram's InlineKeyboardMarkup -
    this helper covers the 90% case where one-button-per-row reads cleanly
    on mobile.

    `callback_data` MUST be 64 bytes or fewer (Telegram cap). Recommended
    format: f"{ping_id}:{verb}" (see module docstring).

    Example:
        kb = build_inline_keyboard([
            ("Commit both",  f"{ping_id}:commit_all"),
            ("Edit",         f"{ping_id}:edit"),
            ("Decline",      f"{ping_id}:decline"),
        ])
    """
    rows = [
        [InlineKeyboardButton(text=label, callback_data=data)]
        for label, data in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_callback_data(data: str) -> tuple[str, str]:
    """Split "{ping_id}:{action}" into (ping_id, action).

    Returns ("", "") if data is malformed (empty, missing colon, etc).
    Callers should treat empty-tuple returns as "stale or non-ours" and
    answer the callback with a benign message.

    The action portion may contain colons (forwards-compatible: a verb like
    "cluster_approve:42" would parse as action="cluster_approve:42"); the
    verb handler is responsible for any further parsing.
    """
    if not data or not isinstance(data, str):
        return "", ""
    if ":" not in data:
        return "", ""
    ping_id, _, action = data.partition(":")
    if not ping_id or not action:
        return "", ""
    return ping_id, action


async def edit_message_after_action(
    bot,
    chat_id: int,
    message_id: int,
    new_text: str,
) -> bool:
    """Edit a message in place, removing its inline keyboard.

    Default pattern after a button is tapped: replace the ping text with
    a status line (e.g. "Done - 3 todos created") and strip the buttons so
    the user can't double-tap. Per A8's UX recommendation.

    Uses HTML parse mode (matches DefaultBotProperties in main.py).
    Returns True on success, False on any Telegram error - callers can
    fall back to bot.send_message() if the edit fails (e.g. message too
    old to edit).
    """
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            reply_markup=None,
            parse_mode="HTML",
        )
        return True
    except Exception:
        return False
