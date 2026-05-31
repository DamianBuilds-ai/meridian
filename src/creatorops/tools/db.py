"""
Shared SQLite connection and schema bootstrap for CreatorOps.

All three tables (contacts, content_calendar, subscribers) are created here
on first use. Every tool imports `get_conn` from this module.

The database path is read from the CREATOROPS_DB_PATH environment variable.
If the variable is not set, /tmp/creatorops.db is used so the bot runs
out of the box without any configuration.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

DB_PATH = os.getenv("CREATOROPS_DB_PATH", "/tmp/creatorops.db")

_DDL = """
CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT,
    platform        TEXT,
    notes           TEXT,
    engagement_count INTEGER DEFAULT 0,
    last_contact_at TEXT    DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS content_calendar (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    platform     TEXT,
    publish_date TEXT    NOT NULL,
    status       TEXT    DEFAULT 'scheduled',
    created_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subscribers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,
    email        TEXT    NOT NULL UNIQUE,
    platform     TEXT,
    subscribed_at TEXT   DEFAULT (date('now'))
);
"""


def _bootstrap(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Yield a bootstrapped SQLite connection. Auto-commits on clean exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _bootstrap(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
