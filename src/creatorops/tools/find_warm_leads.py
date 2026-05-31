"""Cross-dataset intersection: subscribers who are also engaged contacts."""

from agents import function_tool
from creatorops.tools.db import get_conn


@function_tool
async def find_warm_leads() -> str:
    """Find people who are both email subscribers AND engaged contacts.

    These individuals have opted into your list AND have direct engagement
    history - making them the highest-value outreach targets.

    USE WHEN: the user asks who they should prioritise, who is in both
    their contact list and subscriber list, or wants the warmest audience
    segment for a campaign or direct outreach.
    """
    with get_conn() as conn:
        # Cross-dataset intersection: join on normalised lowercase email.
        rows = conn.execute(
            """
            SELECT
                c.id            AS contact_id,
                c.name,
                c.email         AS contact_email,
                c.platform,
                c.engagement_count,
                c.last_contact_at,
                s.subscribed_at
            FROM contacts c
            INNER JOIN subscribers s
                ON lower(trim(c.email)) = lower(trim(s.email))
            WHERE c.engagement_count > 0
              AND c.email IS NOT NULL
              AND c.email != ''
            ORDER BY c.engagement_count DESC, c.last_contact_at DESC
            """
        ).fetchall()

    if not rows:
        return (
            "<b>No warm leads found in the intersection.</b>\n"
            "A warm lead appears here when a person is both an email subscriber "
            "and a contact with engagement_count &gt; 0.\n\n"
            "Try adding contacts with engagement, or add subscribers whose emails "
            "match existing contacts."
        )

    lines = [f"<b>Warm leads</b> - in both subscriber list and contacts ({len(rows)} found)"]
    for i, row in enumerate(rows, start=1):
        platform_tag = f" ({row['platform']})" if row["platform"] else ""
        lines.append(
            f"{i}. <b>{row['name']}</b>{platform_tag} - "
            f"<code>{row['contact_email']}</code> | "
            f"engagements <code>{row['engagement_count']}</code> | "
            f"subscribed <i>{row['subscribed_at']}</i>"
        )
    return "\n".join(lines)
