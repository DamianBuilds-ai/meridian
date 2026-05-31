"""
Shared SQLite setup for the Lighthouse package.

All tables are created in a single database file whose path is set via the
LIGHTHOUSE_DB_PATH environment variable (default: /app/data/lighthouse.db).
Parent directories are created automatically on first use.

Tables:
    tasks          - cross-session task records with domain, status, priority
    findings       - cross-component notes written by record_finding
    memory_fts     - FTS5 virtual table for keyword search over findings + free text
    snoozes        - domain snooze records written by snooze_domain
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _db_path() -> Path:
    raw = os.environ.get("LIGHTHOUSE_DB_PATH", "/app/data/lighthouse.db")
    p = Path(raw)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def connect() -> sqlite3.Connection:
    """Open WAL-mode connection and ensure schema exists."""
    conn = sqlite3.connect(str(_db_path()), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            domain      TEXT    NOT NULL DEFAULT 'general',
            title       TEXT    NOT NULL,
            priority    TEXT    NOT NULL DEFAULT 'normal',  -- low | normal | high | urgent
            status      TEXT    NOT NULL DEFAULT 'open',    -- open | done | cancelled
            due_date    TEXT,                               -- ISO date string or NULL
            created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now')),
            updated_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_domain_status "
        "ON tasks(domain, status)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            component   TEXT    NOT NULL DEFAULT 'general',
            category    TEXT    NOT NULL DEFAULT 'note',   -- note | alert | decision | action
            body        TEXT    NOT NULL,
            created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_findings_component "
        "ON findings(component)"
    )

    # FTS5 virtual table for full-text search over findings.body
    # If FTS5 is not compiled in (rare), the CREATE is silently skipped and
    # search_memory falls back to a LIKE scan.
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
            USING fts5(body, content=findings, content_rowid=id)
        """)
        # Keep FTS index in sync with findings inserts
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS findings_ai
            AFTER INSERT ON findings BEGIN
                INSERT INTO memory_fts(rowid, body) VALUES (new.id, new.body);
            END
        """)
    except sqlite3.OperationalError:
        pass  # FTS5 not available - search_memory uses LIKE fallback

    conn.execute("""
        CREATE TABLE IF NOT EXISTS snoozes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            domain      TEXT    NOT NULL,
            until_ts    INTEGER NOT NULL,  -- unix timestamp: suppress alerts until this time
            reason      TEXT,
            created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_snoozes_domain "
        "ON snoozes(domain)"
    )

    return conn
