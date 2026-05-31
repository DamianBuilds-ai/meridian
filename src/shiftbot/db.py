"""
SQLite setup for ShiftBot.

All tables are created on first use. The DB path is read from
SHIFTBOT_DB_PATH env var; defaults to /tmp/shiftbot.db so the
bot is runnable out of the box without any configuration.
"""

import os
import sqlite3
from pathlib import Path

_DB_PATH: str = os.getenv("SHIFTBOT_DB_PATH", "/tmp/shiftbot.db")
_initialised: bool = False


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not already exist. Idempotent."""
    global _initialised
    if _initialised:
        return
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS shifts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                shift_date  TEXT    NOT NULL,   -- YYYY-MM-DD
                platform    TEXT    NOT NULL,   -- e.g. "rideshare", "delivery", "freelance"
                gross_pay   REAL    NOT NULL,   -- total earnings before deductions
                tips        REAL    NOT NULL DEFAULT 0.0,
                hours       REAL    NOT NULL,   -- hours worked
                km          REAL    NOT NULL DEFAULT 0.0,  -- kilometres driven (0 if N/A)
                notes       TEXT    NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL    -- ISO 8601 UTC
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id           TEXT    PRIMARY KEY,  -- UUID
                user_id      TEXT    NOT NULL,
                expense_date TEXT    NOT NULL,      -- YYYY-MM-DD
                description  TEXT    NOT NULL,
                total_amount REAL    NOT NULL,
                created_at   TEXT    NOT NULL       -- ISO 8601 UTC
            );

            CREATE TABLE IF NOT EXISTS expense_splits (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id   TEXT    NOT NULL REFERENCES expenses(id),
                participant  TEXT    NOT NULL,
                amount_owed  REAL    NOT NULL,
                settled      INTEGER NOT NULL DEFAULT 0  -- 0 = outstanding, 1 = settled
            );
        """)
    _initialised = True


def get_conn() -> sqlite3.Connection:
    """Return an open connection; ensure tables exist first."""
    init_db()
    return _get_conn()
