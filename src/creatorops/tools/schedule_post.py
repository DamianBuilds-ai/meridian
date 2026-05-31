"""Add a post to the content calendar."""

from agents import function_tool
from creatorops.tools.db import get_conn


@function_tool
async def schedule_post(
    title: str,
    publish_date: str,
    platform: str = "",
) -> str:
    """Add a new post to the content calendar.

    USE WHEN: the user wants to plan or schedule content, add a post idea,
    or block a date for publishing.

    Args:
        title: post title or short description
        publish_date: target publish date in YYYY-MM-DD format
        platform: target platform, e.g. "YouTube", "Instagram", "Newsletter"
    """
    # Basic date format validation - reject obviously wrong input early.
    import re as _re
    if not _re.match(r"^\d{4}-\d{2}-\d{2}$", publish_date):
        return (
            "<b>Invalid date format.</b> Please provide the date as "
            "<code>YYYY-MM-DD</code>, for example <code>2025-07-15</code>."
        )

    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO content_calendar (title, platform, publish_date)
            VALUES (?, ?, ?)
            """,
            (title, platform or None, publish_date),
        )
        post_id = cursor.lastrowid

    lines = [
        f"<b>Post scheduled</b> (id {post_id})",
        f"<b>Title:</b> {title}",
        f"<b>Date:</b> {publish_date}",
    ]
    if platform:
        lines.append(f"<b>Platform:</b> {platform}")
    return "\n".join(lines)
