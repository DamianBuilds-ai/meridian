"""Sub-LLM-as-a-tool: draft a personalised reply for a named contact.

This tool showcases the Meridian sub-agent pattern: it spins up a lightweight
sub-agent via Runner.run to do the actual generation, completely decoupled from
the main CreatorOps agent.
"""

from agents import function_tool, Runner
from creatorops.tools.db import get_conn
from shared.telegram_format import sanitize_for_telegram


def _build_drafter_agent():
    """Lazily construct the reply-drafter sub-agent.

    Imported and constructed inside the tool to keep error isolation clean -
    if the sub-agent's model is misconfigured it will only fail when this
    tool is called, not at import time.
    """
    from agents import Agent, ModelSettings
    from shared.model_factory import get_model_for_bot, get_openrouter_extra_body

    return Agent(
        name="creatorops_drafter",
        instructions=(
            "You are a professional creator-outreach ghostwriter. "
            "Given context about a contact and a message goal, write a short, "
            "warm, and direct reply or outreach message. "
            "No more than 150 words. Plain prose only - no bullet points, "
            "no markdown, no HTML tags. Return only the draft text."
        ),
        tools=[],
        model=get_model_for_bot("creatorops_drafter"),
        model_settings=ModelSettings(
            parallel_tool_calls=False,
            tool_choice="auto",
            extra_body=get_openrouter_extra_body(),
        ),
    )


@function_tool
async def draft_reply(contact_name: str, goal: str) -> str:
    """Draft a personalised outreach message or reply for a named contact.

    This tool calls a sub-model to generate the draft. It pulls contact
    context (platform, notes, engagement history) from the CRM and passes
    it to the drafter agent.

    USE WHEN: the user wants to reach out to someone, follow up with a contact,
    or draft a message they will send themselves.

    Args:
        contact_name: name of the contact to write to (partial match supported)
        goal: what the message should achieve, e.g. "follow up after our chat",
              "pitch a collaboration", "say thank you for the shoutout"
    """
    # Retrieve contact context from the CRM.
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT name, email, platform, notes, engagement_count, last_contact_at
            FROM contacts
            WHERE lower(name) LIKE lower(?)
            ORDER BY engagement_count DESC
            LIMIT 1
            """,
            (f"%{contact_name}%",),
        ).fetchone()

    if not row:
        return (
            f"<b>Contact not found:</b> <i>{contact_name}</i>\n"
            "Add them first with <b>add_contact</b>, then try again."
        )

    contact_context = (
        f"Contact name: {row['name']}\n"
        f"Platform: {row['platform'] or 'unknown'}\n"
        f"Notes: {row['notes'] or 'none'}\n"
        f"Engagements recorded: {row['engagement_count']}\n"
        f"Last contact: {row['last_contact_at']}"
    )
    prompt = (
        f"Write a message to this contact.\n\n"
        f"CONTACT CONTEXT:\n{contact_context}\n\n"
        f"MESSAGE GOAL:\n{goal}"
    )

    # Invoke the sub-agent (sub-LLM-as-a-tool pattern).
    drafter = _build_drafter_agent()
    result = await Runner.run(starting_agent=drafter, input=prompt)
    draft_text = result.final_output or "(no draft generated)"
    draft_text = sanitize_for_telegram(draft_text)

    lines = [
        f"<b>Draft for {row['name']}</b>",
        f"<i>Goal: {goal}</i>",
        "",
        draft_text,
    ]
    return "\n".join(lines)
