"""Rank contacts by recency and engagement to surface warm leads."""

from agents import function_tool
from creatorops.tools.db import get_conn


@function_tool
async def score_warm_leads(limit: int = 10) -> str:
    """Rank contacts by a warm-lead score derived from recency and engagement count.

    USE WHEN: the user asks who they should reach out to, who is warm, or
    wants a prioritised outreach list.

    Scoring formula: engagement_count * 2 + days_since_contact_recency_bonus.
    Contacts touched within the last 30 days receive a recency bonus of 10 points.

    Args:
        limit: maximum number of contacts to return (default 10)
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                email,
                platform,
                engagement_count,
                last_contact_at,
                (
                    engagement_count * 2
                    + CASE
                        WHEN julianday('now') - julianday(last_contact_at) <= 30
                        THEN 10
                        ELSE 0
                      END
                ) AS score
            FROM contacts
            ORDER BY score DESC, last_contact_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return "No contacts found. Add some contacts first with <b>add_contact</b>."

    lines = [f"<b>Top {len(rows)} warm leads</b>"]
    for i, row in enumerate(rows, start=1):
        platform_tag = f" ({row['platform']})" if row['platform'] else ""
        email_tag = f" - {row['email']}" if row['email'] else ""
        lines.append(
            f"{i}. <b>{row['name']}</b>{platform_tag}{email_tag} "
            f"| score <code>{row['score']}</code> "
            f"| engagements <code>{row['engagement_count']}</code> "
            f"| last contact <i>{row['last_contact_at']}</i>"
        )
    return "\n".join(lines)
