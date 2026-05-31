"""SQLite-backed pending-ping state for Telegram callback + free-text resolution.

Schema:
    pings(
      ping_id TEXT PRIMARY KEY,        -- 8-char URL-safe random (secrets.token_urlsafe(6))
      bot TEXT NOT NULL,                -- which bot sent the ping
      user_id INTEGER NOT NULL,         -- Telegram user ID (multi-user-ready)
      chat_id INTEGER NOT NULL,         -- Telegram chat ID
      message_id INTEGER NOT NULL,      -- Telegram message_id of the ping
      context_json TEXT NOT NULL,       -- JSON blob: {kind, payload, items, ...}
      created_at INTEGER NOT NULL,      -- unix timestamp (seconds)
      expires_at INTEGER NOT NULL,      -- unix timestamp (seconds), default +60min
      status TEXT NOT NULL DEFAULT 'pending'  -- pending | acked | expired
    )

Indexes:
    idx_chat_status(chat_id, status)    -- fast "active pings in this chat" lookup
    idx_expires(expires_at)             -- fast expiry sweep

DB path is env-driven via PING_STATE_DB_PATH (default: /app/data/pings.db -
the docker-compose-mounted bot data directory). Parent dir auto-created.
WAL mode is enabled to avoid writer-lock contention between the callback
handler and the free-text-context-injection reader (both fire from the
same aiogram event loop but Python's sqlite3 wrapper releases the GIL on
COMMIT; WAL keeps readers non-blocking).

All functions are async-friendly (sqlite3 itself is sync, but we keep the
signatures `async def` so callers don't have to switch contexts when we
eventually move to aiosqlite). No I/O outside this module's surface.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path


def _db_path() -> Path:
    raw = os.environ.get("PING_STATE_DB_PATH", "/app/data/pings.db")
    p = Path(raw)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    """Open the SQLite connection + ensure the schema + indexes exist.

    WAL mode is enabled per-connection (Telegram default-connection pragma
    is journaled mode, which serialises readers behind any pending writer).
    """
    conn = sqlite3.connect(str(_db_path()), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pings (
            ping_id TEXT PRIMARY KEY,
            bot TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            context_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_status "
        "ON pings(chat_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expires ON pings(expires_at)"
    )
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "ping_id": row["ping_id"],
        "bot": row["bot"],
        "user_id": int(row["user_id"]),
        "chat_id": int(row["chat_id"]),
        "message_id": int(row["message_id"]),
        "context": json.loads(row["context_json"] or "{}"),
        "created_at": int(row["created_at"]),
        "expires_at": int(row["expires_at"]),
        "status": row["status"],
    }


async def create_ping(
    bot: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    context: dict,
    ttl_min: int = 60,
) -> str:
    """Persist a new ping and return its 8-char ping_id.

    `context` is JSON-serialised. Common shapes:
        {"kind": "urgent_email", "items": [{"sender": "Atlas", "subject": "..."}]}
        {"kind": "hermes_task", "items": [{"title": "Fix the door", "priority": "low"}]}
        {"kind": "voice_capture", "raw_transcript": "...", "draft_task": {...}}

    Collisions on the 8-char id are negligible (URL-safe base64 of 6 bytes =
    2^48 space), but if one occurs the INSERT raises sqlite3.IntegrityError
    and the caller can retry.
    """
    ping_id = secrets.token_urlsafe(6)  # 8 chars - fits Telegram's 64-byte callback cap
    now = int(time.time())
    expires = now + (ttl_min * 60)
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO pings "
            "(ping_id, bot, user_id, chat_id, message_id, context_json, "
            " created_at, expires_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
            (
                ping_id, bot, int(user_id), int(chat_id), int(message_id),
                json.dumps(context or {}), now, expires,
            ),
        )
    finally:
        conn.close()
    return ping_id


async def get_ping(ping_id: str) -> dict | None:
    """Fetch one ping by id. Returns the full row as a dict, or None if missing."""
    if not ping_id:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM pings WHERE ping_id = ?",
            (ping_id,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row else None


async def get_pending_pings(chat_id: int, max_count: int = 3) -> list[dict]:
    """Return up to `max_count` most-recent pending pings for the chat.

    Used by the free-text handler to inject pending-ping context into the
    LLM prompt. Capped at 3 by default to keep prompt bloat bounded; the
    user's reply almost always refers to the most recent ping anyway.

    Filters: status = 'pending' AND not yet expired.
    Orders: most-recent first (DESC by created_at).
    """
    if not chat_id:
        return []
    now = int(time.time())
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM pings "
            "WHERE chat_id = ? AND status = 'pending' AND expires_at > ? "
            "ORDER BY created_at DESC LIMIT ?",
            (int(chat_id), now, int(max_count)),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


async def ack_ping(ping_id: str, result: dict | str | None = None) -> bool:
    """Mark a ping as acked. Stores `result` (audit trail) into context_json.

    Returns True if the ping was updated, False if it didn't exist.

    The result is merged into the existing context_json under the key
    `ack_result` so we keep both the original ping payload AND what happened.
    Useful for future inspection / debugging / replay.
    """
    if not ping_id:
        return False
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT context_json FROM pings WHERE ping_id = ?",
            (ping_id,),
        ).fetchone()
        if not row:
            return False
        ctx = json.loads(row["context_json"] or "{}")
        ctx["ack_result"] = result if result is not None else "acked"
        ctx["acked_at"] = int(time.time())
        conn.execute(
            "UPDATE pings SET status = 'acked', context_json = ? "
            "WHERE ping_id = ?",
            (json.dumps(ctx), ping_id),
        )
    finally:
        conn.close()
    return True


async def expire_stale_pings() -> int:
    """Mark all pending pings past their expires_at as 'expired'. Returns count.

    Intended for periodic call (cron, periodic task, or lazy from get_pending_pings).
    The query is idempotent - running it twice is harmless.
    """
    now = int(time.time())
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE pings SET status = 'expired' "
            "WHERE status = 'pending' AND expires_at <= ?",
            (now,),
        )
        return cur.rowcount or 0
    finally:
        conn.close()
