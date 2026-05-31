"""
Session management - SQLite-backed conversation history.

Stores full tool_call + tool_result messages. This is THE fix for
n8n's ghost execution bug. The model always sees its complete history.

Each user+bot combination gets its own session_id so conversations
don't bleed across users or bots.

Context window: per-bot limit (see SESSION_MESSAGE_LIMITS). Older
items are still in the DB but not sent to the model. This prevents
token bloat while keeping enough recent history for natural
conversation. Light bots use a smaller window; heavier reasoning bots
get more headroom.

TTL pruning: rows older than the per-bot TTL are deleted on get_session
(rate-limited to once per 5 min per session). The latest N messages are
always preserved as a floor (cold-restart anchor). Best-effort - prune
failures never break message flow.

Orphan-tool sanitation: when the read window slices mid-tool-cycle the
truncated list can start with (or contain) a `function_call_output`
whose matching `function_call` got cut off. vLLM rejects this with
HTTP 400 ("Unexpected role 'tool'" / "Unexpected tool call id ...").
SanitizedSQLiteSession overrides get_items() to drop these orphans
before returning the window to the SDK.
"""

import sqlite3
import time

from agents import SQLiteSession, SessionSettings

SESSION_DB_PATH = "/app/data/sessions.db"

# Per-bot read-window limits. Each turn is roughly
# user msg + tool_call + tool_result + assistant response (~4 items).
SESSION_MESSAGE_LIMITS = {
    # Add your bots here to override the default read window.
    # Each turn is roughly 4 items (user msg + tool_call + tool_result + response).
    # Example: "assistant": 20,
}
DEFAULT_SESSION_LIMIT = 30

# Per-bot TTL in hours. Rows older than this get pruned (subject to floor).
SESSION_TTL_HOURS = {
    # Add per-bot TTL overrides here. Example: "assistant": 12,
}
DEFAULT_SESSION_TTL_HOURS = 24

PRUNE_RATE_LIMIT_SECONDS = 300  # 5 min per session
_last_prune_at: dict[str, float] = {}  # session_id -> monotonic timestamp


def _prune_session_if_due(session_id: str, bot_name: str) -> int:
    """Prune rows older than per-bot TTL, preserving latest-N floor.

    Rate-limited to once per PRUNE_RATE_LIMIT_SECONDS per session.
    Returns number of rows deleted (0 if rate-limited or no-op).
    Failures are swallowed - pruning is best-effort hygiene, not load-bearing.
    """
    now = time.monotonic()
    last = _last_prune_at.get(session_id, 0.0)
    if now - last < PRUNE_RATE_LIMIT_SECONDS:
        return 0

    ttl_hours = SESSION_TTL_HOURS.get(bot_name, DEFAULT_SESSION_TTL_HOURS)
    read_limit = SESSION_MESSAGE_LIMITS.get(bot_name, DEFAULT_SESSION_LIMIT)
    floor = min(read_limit, 10)
    ttl_offset = f"-{ttl_hours} hours"

    try:
        conn = sqlite3.connect(SESSION_DB_PATH, timeout=2.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.execute(
                """
                DELETE FROM agent_messages
                WHERE session_id = ?
                  AND created_at < datetime('now', ?)
                  AND id NOT IN (
                    SELECT id FROM agent_messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (session_id, ttl_offset, session_id, floor),
            )
            conn.commit()
            deleted = cur.rowcount or 0
        finally:
            conn.close()
        _last_prune_at[session_id] = now
        return deleted
    except sqlite3.OperationalError:
        # Table may not exist yet (first-ever call before SDK init). Safe to skip.
        _last_prune_at[session_id] = now
        return 0
    except Exception:
        # Best-effort only - never break message flow on prune failure.
        return 0


def _sanitize_messages(items):
    """Strip orphan tool-result items from a truncated read window.

    The Agents SDK stores typed items in SQLite. Tool calls are
    `{"type": "function_call", "call_id": "...", ...}` and tool results
    are `{"type": "function_call_output", "call_id": "...", ...}`.
    Neither has a `role` key. Plain chat messages have `role` in
    {"user", "assistant", "system"}.

    When SQLiteSession truncates to the latest N items, the slice can
    leave a function_call_output whose matching function_call was cut
    off. vLLM rejects those windows. This function:

      1. Drops any *leading* items that are function_call_output (their
         function_call certainly got sliced).
      2. Walks remaining items; drops any function_call_output whose
         call_id has no preceding function_call in the kept window.

    Best-effort and pure - never raises. If the structure is unfamiliar
    (e.g. SDK schema change), returns the input unchanged.
    """
    if not items:
        return items

    try:
        # Phase 1: drop leading orphan function_call_output items.
        start = 0
        while start < len(items):
            it = items[start]
            if isinstance(it, dict) and it.get("type") == "function_call_output":
                start += 1
                continue
            break
        cleaned = items[start:]

        # Phase 2: collect call_ids from any function_call items present.
        valid_call_ids = set()
        for it in cleaned:
            if isinstance(it, dict) and it.get("type") == "function_call":
                cid = it.get("call_id")
                if cid:
                    valid_call_ids.add(cid)

        # Phase 3: drop function_call_output items with no matching call.
        final = []
        for it in cleaned:
            if isinstance(it, dict) and it.get("type") == "function_call_output":
                cid = it.get("call_id")
                if not cid or cid not in valid_call_ids:
                    continue
            final.append(it)

        return final
    except Exception:
        # Sanitation must never break message flow.
        return items


class SanitizedSQLiteSession(SQLiteSession):
    """SQLiteSession that strips orphan tool-result items from the read window.

    Transparent wrapper - the SDK only calls add_items() and get_items()
    on the session, so overriding get_items() is sufficient. add_items()
    inherits unchanged: we never want to filter items going IN, only
    what comes OUT after truncation.
    """

    async def get_items(self, limit: int | None = None):
        items = await super().get_items(limit=limit)
        return _sanitize_messages(items)


def get_session(bot_name: str, user_id: int) -> SQLiteSession:
    """Get a session for a specific user and bot combination.

    Prunes TTL-expired rows before returning (rate-limited, best-effort).
    Returns a SanitizedSQLiteSession that drops orphan tool-result items
    from the truncated read window.
    """
    session_id = f"{bot_name}_{user_id}"
    _prune_session_if_due(session_id, bot_name)
    limit = SESSION_MESSAGE_LIMITS.get(bot_name, DEFAULT_SESSION_LIMIT)
    settings = SessionSettings(limit=limit)
    return SanitizedSQLiteSession(
        session_id,
        SESSION_DB_PATH,
        session_settings=settings,
    )
