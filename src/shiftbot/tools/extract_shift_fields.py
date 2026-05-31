"""
Upstream OCR / vision extractor for ShiftBot.

This module is intentionally decoupled from the agent so that the
vision step can be swapped independently (Gemini vision, Tesseract,
a third-party receipt-parsing API, etc.) without touching agent logic.

The agent NEVER calls a vision model directly. The caller (e.g. a
Telegram photo handler) runs extract_shift_fields_from_image(), then
passes the returned dict to the log_shift tool as keyword arguments.

STUB IMPLEMENTATION
-------------------
The function below returns hard-coded example data that matches the
shape the real extractor must return. Replace the body with your
chosen backend before going live.

TODO: replace this stub with a real implementation. Options:
  - Gemini Vision API (see https://ai.google.dev/gemini-api/docs/vision)
  - OpenAI GPT-4o vision (see https://platform.openai.com/docs/guides/vision)
  - Tesseract OCR via pytesseract (see https://github.com/madmaze/pytesseract)
  - A commercial receipt-parsing service (see docs/adding-a-bot.md)

The returned dict keys MUST match the parameter names of log_shift:
  shift_date, platform, gross_pay, tips, hours, km, notes
"""

from __future__ import annotations


async def extract_shift_fields_from_image(image_bytes: bytes) -> dict:
    """Extract earnings fields from a screenshot or receipt image.

    Args:
        image_bytes: Raw image data (JPEG, PNG, or WebP).

    Returns:
        A dict with keys: shift_date, platform, gross_pay, tips, hours,
        km, notes. Values are strings/floats ready to pass to log_shift.
        If a field cannot be extracted, its value is an empty string or 0.0.
    """
    # ------------------------------------------------------------------
    # STUB: returns illustrative example data so the rest of the bot is
    # fully exercisable without a real vision backend.
    # ------------------------------------------------------------------
    _ = image_bytes  # unused until stub is replaced
    return {
        "shift_date": "2025-06-15",
        "platform": "rideshare",
        "gross_pay": 87.50,
        "tips": 12.00,
        "hours": 4.5,
        "km": 63.2,
        "notes": "Extracted from screenshot - stub data, replace with real OCR",
    }
