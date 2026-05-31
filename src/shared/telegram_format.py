"""
Telegram formatting utilities.

Converts markdown to Telegram HTML, strips unsupported tags,
and sanitizes model output for Telegram's limited HTML parser.
Used by all bots in the Meridian fleet.
"""

import re


def sanitize_for_telegram(text: str) -> str:
    """Convert any markdown in model output to Telegram-safe HTML.

    Telegram supports only: <b>, <i>, <code>, <pre>, <a>, <s>, <u>.
    Models (especially Mistral) often output markdown even when told not to.
    This catches it at the transport layer so it never reaches the user raw.
    """
    # Replace m-dashes with regular dashes
    text = text.replace("\u2014", "-")  # em dash
    text = text.replace("\u2013", "-")  # en dash

    # Markdown bold **text** -> <b>text</b> (do before italic)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)

    # Markdown italic *text* -> <i>text</i> (but not inside <b> tags already)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Markdown code `text` -> <code>text</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Markdown headers # text -> <b>text</b>
    text = re.sub(r"^#{1,3}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # Markdown bullet points - text or * text -> just the text with line break
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)

    # Strip ALL unsupported HTML tags (Telegram only supports: b, i, code, pre, a, s, u, blockquote)
    # This catches model artifacts like <tool_response>, <think>, <|im_start|>, etc.
    ALLOWED_TAGS = r"b|i|code|pre|a|s|u|blockquote"
    text = re.sub(
        rf"</?(?!(?:{ALLOWED_TAGS})\b)[a-zA-Z_|][^>]*>",
        "",
        text,
    )

    return text


def strip_markdown(text: str) -> str:
    """Strip markdown formatting from text, leaving plain text.

    Used to clean Outline doc content before passing to the model,
    so the model doesn't see markdown and mimic it.
    """
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\*(.+?)\*", r"\1", text)

    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)

    # Remove bullet markers
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)

    # Replace m-dashes
    text = text.replace("\u2014", "-")
    text = text.replace("\u2013", "-")

    return text
