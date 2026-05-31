"""Return aggregate counts across all three CreatorOps data sets."""

from agents import function_tool
from creatorops.tools.db import get_conn


@function_tool
async def audience_snapshot() -> str:
    """Return a high-level summary of contacts, scheduled content, and subscribers.

    USE WHEN: the user asks for an overview, a summary, or "how am I doing"
    style questions about their creator operations.
    """
    with get_conn() as conn:
        total_contacts: int = conn.execute(
            "SELECT COUNT(*) FROM contacts"
        ).fetchone()[0]

        engaged_contacts: int = conn.execute(
            "SELECT COUNT(*) FROM contacts WHERE engagement_count > 0"
        ).fetchone()[0]

        upcoming_posts: int = conn.execute(
            "SELECT COUNT(*) FROM content_calendar "
            "WHERE publish_date >= date('now') AND status != 'archived'"
        ).fetchone()[0]

        total_subscribers: int = conn.execute(
            "SELECT COUNT(*) FROM subscribers"
        ).fetchone()[0]

        new_subscribers_30d: int = conn.execute(
            "SELECT COUNT(*) FROM subscribers "
            "WHERE subscribed_at >= date('now', '-30 days')"
        ).fetchone()[0]

        top_platform = conn.execute(
            """
            SELECT platform, COUNT(*) as cnt
            FROM contacts
            WHERE platform IS NOT NULL
            GROUP BY platform
            ORDER BY cnt DESC
            LIMIT 1
            """
        ).fetchone()

    lines = [
        "<b>Audience snapshot</b>",
        "",
        "<b>Contacts</b>",
        f"  Total: <code>{total_contacts}</code>",
        f"  With engagement: <code>{engaged_contacts}</code>",
        "",
        "<b>Content calendar</b>",
        f"  Upcoming posts: <code>{upcoming_posts}</code>",
        "",
        "<b>Subscribers</b>",
        f"  Total: <code>{total_subscribers}</code>",
        f"  New (last 30 days): <code>{new_subscribers_30d}</code>",
    ]
    if top_platform and top_platform["platform"]:
        lines += [
            "",
            f"<b>Top platform:</b> {top_platform['platform']} "
            f"(<code>{top_platform['cnt']}</code> contacts)",
        ]
    return "\n".join(lines)
