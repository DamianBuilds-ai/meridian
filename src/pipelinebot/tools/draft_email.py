"""draft_email tool - generates a context-aware follow-up email draft."""

from agents import function_tool
from pipelinebot._db import _conn

# TODO: To actually send emails, replace the stub below with a real provider call.
# Transactional email options:
#   - Resend: https://resend.com/docs/api-reference/emails/send-email
#   - Mailgun: https://documentation.mailgun.com/docs/mailgun/api-reference/openapi-final/tag/Messages/
#   - SMTP via smtplib (Python stdlib) if you self-host
# For now the tool returns a formatted draft for the user to copy-paste or review.

_TEMPLATES: dict[str, str] = {
    "prospect": (
        "Subject: Introduction - {sender_name} from {sender_company}\n\n"
        "Hi {name},\n\n"
        "I wanted to reach out because {custom_note}\n\n"
        "Would you have 20 minutes this week for a quick call? I'd love to share how we've "
        "helped similar businesses achieve measurable results.\n\n"
        "Best regards,\n{sender_name}"
    ),
    "qualified": (
        "Subject: Following up on our conversation\n\n"
        "Hi {name},\n\n"
        "It was great connecting with you. As discussed, {custom_note}\n\n"
        "I'm happy to send across any further details or arrange a demo - just let me know "
        "what would be most useful.\n\n"
        "Best regards,\n{sender_name}"
    ),
    "proposal": (
        "Subject: Proposal follow-up - {company}\n\n"
        "Hi {name},\n\n"
        "I wanted to follow up on the proposal I sent across. {custom_note}\n\n"
        "Please don't hesitate to reach out with any questions. I'm available for a call "
        "this week if it would help to walk through the details together.\n\n"
        "Best regards,\n{sender_name}"
    ),
    "negotiation": (
        "Subject: Next steps - {company}\n\n"
        "Hi {name},\n\n"
        "Thank you for your patience as we work through the details. {custom_note}\n\n"
        "I'll be in touch shortly with an update. In the meantime, feel free to reach out "
        "directly if anything comes up.\n\n"
        "Best regards,\n{sender_name}"
    ),
    "default": (
        "Subject: Following up - {company}\n\n"
        "Hi {name},\n\n"
        "{custom_note}\n\n"
        "Looking forward to hearing from you.\n\n"
        "Best regards,\n{sender_name}"
    ),
}


@function_tool
async def draft_email(
    contact_id: int,
    custom_note: str,
    sender_name: str = "Your Name",
    sender_company: str = "Your Company",
) -> str:
    """Generate a context-aware follow-up email draft for a contact.

    USE WHEN: the user asks to write, draft, or compose an email or message to a contact.
    Always use this tool rather than writing an email freehand in chat.

    NOTE: This tool returns a draft for review only. To send automatically, integrate
    a transactional email provider - see the TODO comment in draft_email.py.

    Args:
        contact_id: the integer ID from search_contacts.
        custom_note: a one or two sentence context note to personalise the email
                     (e.g. "you mentioned they're evaluating us against two other vendors").
        sender_name: the rep's name (defaults to placeholder - caller should supply).
        sender_company: the rep's company name (defaults to placeholder).
    """
    with _conn() as con:
        contact = con.execute(
            "SELECT id, name, company, email, stage FROM contacts WHERE id = ? AND pending_delete = 0",
            (contact_id,),
        ).fetchone()

    if not contact:
        return f"<b>Error:</b> No active contact with ID <code>{contact_id}</code>."

    stage = contact["stage"]
    template = _TEMPLATES.get(stage, _TEMPLATES["default"])

    draft = template.format(
        name=contact["name"].split()[0],  # first name
        company=contact["company"],
        custom_note=custom_note,
        sender_name=sender_name,
        sender_company=sender_company,
    )

    return (
        f"<b>Draft email for {contact['name']}</b> ({contact['email'] or 'no email on file'})\n"
        f"Stage: <code>{stage}</code>\n\n"
        f"<code>{draft}</code>\n\n"
        "<i>Review and edit before sending. To auto-send, connect a transactional email "
        "provider - see docs/adding-a-bot.md for guidance.</i>"
    )
