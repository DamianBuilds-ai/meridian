"""
search_notes - Full-text keyword search over the local SQLite notes store.
"""

from agents import function_tool
from aria.db import get_db


@function_tool
async def search_notes(query: str, limit: int = 5) -> str:
    """Search notes by keyword and return matching titles and excerpts.

    USE WHEN: The user asks to find, look up, or search notes. Also call this
    when the user references "what I wrote about X" or "do I have a note on X".

    Args:
        query: Keyword or phrase to search for in note titles and bodies.
        limit: Maximum number of results to return. Default 5.
    """
    if not query.strip():
        return "<i>Please provide a search term.</i>"

    # SQLite LIKE search across title, body, and tags
    pattern = f"%{query.strip()}%"
    limit = max(1, min(limit, 20))

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, title, body, tags
            FROM notes
            WHERE title LIKE ? OR body LIKE ? OR tags LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()

    if not rows:
        return f"<i>No notes found matching <b>{query}</b>.</i>"

    lines = [f"<b>Notes matching '{query}'</b> ({len(rows)} result{'s' if len(rows) != 1 else ''}):"]
    for row in rows:
        # Show up to 120 chars of the body as a snippet
        snippet = row["body"].replace("\n", " ")[:120]
        if len(row["body"]) > 120:
            snippet += "..."
        tags_str = f" [{row['tags']}]" if row["tags"] else ""
        lines.append(
            f"\n<b>#{row['id']} {row['title']}</b>{tags_str}\n<i>{snippet}</i>"
        )

    return "\n".join(lines)
