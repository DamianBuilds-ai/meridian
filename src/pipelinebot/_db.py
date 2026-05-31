"""
Internal SQLite helpers for PipelineBot.

All tools import from here. Tables are created on first use.
DB path is read from the PIPELINE_DB_PATH env var (default: /tmp/pipelinebot.db).
"""

import os
import sqlite3
from contextlib import contextmanager

_DB_PATH = os.getenv("PIPELINE_DB_PATH", "/tmp/pipelinebot.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    company       TEXT    NOT NULL DEFAULT '',
    email         TEXT    NOT NULL DEFAULT '',
    phone         TEXT    NOT NULL DEFAULT '',
    stage         TEXT    NOT NULL DEFAULT 'prospect',
    notes         TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    pending_delete INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS interactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id    INTEGER NOT NULL REFERENCES contacts(id),
    type          TEXT    NOT NULL DEFAULT 'call',
    summary       TEXT    NOT NULL DEFAULT '',
    outcome       TEXT    NOT NULL DEFAULT '',
    next_action   TEXT    NOT NULL DEFAULT '',
    logged_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS followups (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id    INTEGER NOT NULL REFERENCES contacts(id),
    due_date      TEXT    NOT NULL,
    action        TEXT    NOT NULL DEFAULT '',
    done          INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def _conn():
    """Yield a configured SQLite connection and commit/close on exit."""
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they do not already exist."""
    with _conn() as con:
        con.executescript(_SCHEMA)


def seed_demo_contacts() -> None:
    """Insert illustrative contacts if the contacts table is empty.

    This makes the bot immediately useful for a demo without any setup.
    Remove this call (or the seed data) once real contacts are imported.
    """
    with _conn() as con:
        count = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        if count > 0:
            return
        demo = [
            ("Alice Brennan",   "Acme Corp",       "alice@acmecorp.example",   "+15550001111", "qualified",   "Interested in the enterprise plan"),
            ("Ben Nakamura",    "Bright Futures",  "ben@brightfutures.example", "+15550002222", "proposal",    "Sent proposal 2024-11-01; awaiting sign-off"),
            ("Clara Osei",      "Greenleaf Ltd",   "clara@greenleaf.example",   "+15550003333", "prospect",    "Met at trade show; warm intro"),
            ("David Park",      "Ironbridge Co",   "david@ironbridge.example",  "+15550004444", "negotiation", "Discount requested; checking with mgmt"),
            ("Eva Reyes",       "Sunwave Tech",    "eva@sunwave.example",       "+15550005555", "prospect",    "Cold outreach; no response yet"),
            ("Fatima Yilmaz",   "Cornerstone HQ",  "fatima@cornerstone.example","+15550006666", "qualified",   "Call booked for next week"),
        ]
        con.executemany(
            "INSERT INTO contacts (name, company, email, phone, stage, notes) VALUES (?,?,?,?,?,?)",
            demo,
        )
        # Seed some follow-ups due today for the demo action queue
        import datetime
        today = datetime.date.today().isoformat()
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        con.executemany(
            "INSERT INTO followups (contact_id, due_date, action) VALUES (?,?,?)",
            [
                (1, today,    "Follow up on pricing discussion"),
                (2, today,    "Check if proposal was reviewed"),
                (4, today,    "Send revised terms"),
                (3, tomorrow, "Schedule discovery call"),
            ],
        )


# Initialise tables at import time so tools never need to call init explicitly.
init_db()
seed_demo_contacts()
