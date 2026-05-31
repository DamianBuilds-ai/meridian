"""
Australian phone number normalization.
"""

import re


def normalize_phone(phone: str) -> str:
    """
    Normalize an Australian phone number to +61 format.

    Handles: 0412345678, +61412345678, 61412345678, 04 1234 5678
    """
    # Strip everything except digits and leading +
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Remove leading +
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # Remove leading 61 country code
    if cleaned.startswith("61") and len(cleaned) > 10:
        cleaned = cleaned[2:]

    # Remove leading 0
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]

    # Should be 9 digits now (Australian mobile/landline without prefix)
    if len(cleaned) == 9:
        return f"+61{cleaned}"

    # Return original if we can't normalize
    return phone


def extract_phone(text: str) -> str | None:
    """Extract an Australian phone number from text."""
    patterns = [
        r"(\+?61\s?\d[\d\s]{8,10})",   # +61 or 61 prefix
        r"(0[2-9][\d\s]{8,10})",        # 0X prefix
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_phone(match.group(1))
    return None
