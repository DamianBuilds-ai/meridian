"""
free_slots - Computes free time blocks from a list of busy intervals on a given day.
"""

from __future__ import annotations

import re
from agents import function_tool
from shared.dates import local_now, format_date


def _parse_hhmm(s: str) -> int:
    """Parse HH:MM string into minutes since midnight. Returns -1 on failure."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", s.strip())
    if not m:
        return -1
    return int(m.group(1)) * 60 + int(m.group(2))


def _fmt_mins(mins: int) -> str:
    """Format minutes-since-midnight as HH:MM."""
    return f"{mins // 60:02d}:{mins % 60:02d}"


@function_tool
async def free_slots(
    busy_blocks: str,
    day_start: str = "09:00",
    day_end: str = "18:00",
    min_slot_minutes: int = 30,
    date_label: str = "",
) -> str:
    """Find free time slots given a list of busy blocks for a day.

    USE WHEN: The user asks when they are free, wants to schedule something, or
    asks for available slots on a day.

    Args:
        busy_blocks:      Comma-separated list of busy intervals in HH:MM-HH:MM format.
                          Example: "09:00-10:00,12:00-13:30,15:00-16:00"
                          Pass an empty string if no busy blocks.
        day_start:        Start of the working day in HH:MM. Default "09:00".
        day_end:          End of the working day in HH:MM. Default "18:00".
        min_slot_minutes: Minimum free slot length in minutes to report. Default 30.
        date_label:       Human label for the day, e.g. "Monday 2 June". If empty,
                          defaults to today's date.
    """
    start_mins = _parse_hhmm(day_start)
    end_mins = _parse_hhmm(day_end)

    if start_mins < 0 or end_mins < 0 or start_mins >= end_mins:
        return "<i>Invalid day_start or day_end. Use HH:MM format.</i>"

    # Parse busy blocks
    busy: list[tuple[int, int]] = []
    if busy_blocks.strip():
        for block in busy_blocks.split(","):
            parts = block.strip().split("-")
            if len(parts) != 2:
                continue
            s = _parse_hhmm(parts[0])
            e = _parse_hhmm(parts[1])
            if s >= 0 and e > s:
                busy.append((s, e))

    # Sort and merge overlapping busy blocks
    busy.sort()
    merged: list[tuple[int, int]] = []
    for s, e in busy:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append([s, e])

    # Walk the day and collect free gaps
    free: list[tuple[int, int]] = []
    cursor = start_mins
    for bs, be in merged:
        bs = max(bs, start_mins)
        be = min(be, end_mins)
        if bs > cursor:
            free.append((cursor, bs))
        cursor = max(cursor, be)
    if cursor < end_mins:
        free.append((cursor, end_mins))

    # Filter by minimum length
    free = [(s, e) for s, e in free if (e - s) >= min_slot_minutes]

    date_str = date_label or format_date(local_now())
    if not free:
        return (
            f"<b>Free slots on {date_str}</b>\n"
            f"<i>No free slots of {min_slot_minutes}+ minutes found within "
            f"{_fmt_mins(start_mins)}-{_fmt_mins(end_mins)}.</i>"
        )

    lines = [f"<b>Free slots on {date_str}</b> ({_fmt_mins(start_mins)}-{_fmt_mins(end_mins)}):"]
    for s, e in free:
        duration = e - s
        hours, mins = divmod(duration, 60)
        dur_str = (f"{hours}h " if hours else "") + (f"{mins}m" if mins else "")
        lines.append(f"  {_fmt_mins(s)} - {_fmt_mins(e)}  ({dur_str.strip()})")

    return "\n".join(lines)
