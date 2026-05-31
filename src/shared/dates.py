"""
Date utilities - configurable timezone, business day calculation.

Set BOT_TIMEZONE to any IANA timezone string (e.g. "America/New_York", "Europe/London").
Defaults to "UTC" if not set.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BOT_TZ = ZoneInfo(os.getenv("BOT_TIMEZONE", "UTC"))
_TZ_LABEL = os.getenv("TZ_LABEL", os.getenv("BOT_TIMEZONE", "UTC"))


def local_now() -> datetime:
    """Current datetime in the configured BOT_TIMEZONE."""
    return datetime.now(BOT_TZ)


def local_today() -> datetime:
    """Today at midnight in the configured BOT_TIMEZONE."""
    now = local_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def add_business_days(start: datetime, days: int) -> datetime:
    """Add N business days (skip weekends) to a date."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            added += 1
    return current


def parse_followup_timeframe(text: str, base: datetime | None = None) -> datetime:
    """
    Parse a natural language timeframe into a datetime.

    Supports: "tomorrow", "X days", "X weeks", "X months",
    "next monday", "this friday", etc.
    """
    if base is None:
        base = local_now()

    text_lower = text.lower().strip()

    # Tomorrow
    if "tomorrow" in text_lower:
        result = base + timedelta(days=1)
        if result.weekday() >= 5:
            result = add_business_days(base, 1)
        return result.replace(hour=9, minute=0, second=0, microsecond=0)

    # X days
    for word in text_lower.split():
        if word.isdigit():
            num = int(word)
            if "week" in text_lower:
                return (base + timedelta(weeks=num)).replace(hour=9, minute=0, second=0, microsecond=0)
            elif "month" in text_lower:
                return (base + timedelta(days=num * 30)).replace(hour=9, minute=0, second=0, microsecond=0)
            else:
                return add_business_days(base, num).replace(hour=9, minute=0, second=0, microsecond=0)

    # Next [weekday]
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    for day_name, day_num in weekdays.items():
        if day_name in text_lower:
            days_ahead = day_num - base.weekday()
            if "next" in text_lower:
                days_ahead += 7
            if days_ahead <= 0:
                days_ahead += 7
            return (base + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)

    # Default: 3 business days
    return add_business_days(base, 3).replace(hour=9, minute=0, second=0, microsecond=0)


def format_date(dt: datetime) -> str:
    """Format a datetime for display."""
    return dt.strftime("%a %d %b %Y")


def format_datetime(dt: datetime) -> str:
    """Format a datetime with time for display."""
    return dt.strftime("%a %d %b %Y %H:%M")


def to_iso(dt: datetime) -> str:
    """Format a datetime as ISO 8601 (UTC, no microseconds)."""
    from zoneinfo import ZoneInfo
    utc_dt = dt.astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
