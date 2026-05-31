"""
SQLite initialiser for Aria.

All tables are created on first import. Path comes from the ARIA_DB_PATH
environment variable; falls back to aria.db in the working directory.
"""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("ARIA_DB_PATH", "aria.db")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT    NOT NULL,
            due_date  TEXT,
            priority  TEXT    DEFAULT 'medium',
            status    TEXT    DEFAULT 'open',
            created   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT    NOT NULL,
            body      TEXT    NOT NULL,
            tags      TEXT    DEFAULT '',
            created   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS session_context (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            summary   TEXT    NOT NULL,
            saved_at  TEXT    NOT NULL
        );
        """
    )
    conn.commit()


@contextmanager
def get_db():
    """Yield an initialised SQLite connection. Closes on exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    try:
        yield conn
    finally:
        conn.close()
