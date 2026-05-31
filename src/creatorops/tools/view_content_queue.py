"""Return upcoming scheduled posts from the content calendar."""

from agents import function_tool
from creatorops.tools.db import get_conn


@function_tool
async def view_content_queue(limit: int = 20) -> str:
    """Show all upcoming scheduled posts ordered by publish date (soonest first).

    USE WHEN: the user asks what is coming up, wants to see the content plan,
    or asks what is on the calendar.

    Args:
        limit: maximum number of posts to return (default 20)
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, platform, publish_date, status
            FROM content_calendar
            WHERE publish_date >= date('now')
              AND status != 'archived'
            ORDER BY publish_date ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return (
            "No upcoming posts scheduled. "
            "Use <b>schedule_post</b> to add content to the calendar."
        )

    lines = [f"<b>Content queue</b> ({len(rows)} upcoming)"]
    for row in rows:
        platform_tag = f" [{row['platform']}]" if row['platform'] else ""
        lines.append(
            f"<code>{row['publish_date']}</code>{platform_tag} - {row['title']} "
            f"<i>({row['status']})</i>"
        )
    return "\n".join(lines)
