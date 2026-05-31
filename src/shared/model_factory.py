"""
Model factory - returns the right LLM client for each bot.

Routing is driven by config.BOT_MODEL_MAP. Anything not listed defaults
to Mistral.

NOTE: The local Ollama path is not in the default routing map.
To enable self-hosted inference, set OLLAMA_URL in .env and add an
OllamaCompatClient wrapper plus an "ollama" branch here.
"""

from openai import AsyncOpenAI
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from shared.mistral_compat import MistralCompatClient
from shared.gemini_compat import GeminiCompatClient
from config import settings, BOT_MODEL_MAP

try:
    from config import BOT_MODEL_MAP_SUBAGENTS
except ImportError:
    BOT_MODEL_MAP_SUBAGENTS = {}


_clients: dict[str, object] = {}


def _get_mistral():
    if "mistral" not in _clients:
        _clients["mistral"] = MistralCompatClient(
            base_url="https://api.mistral.ai/v1",
            api_key=settings.mistral_api_key or "not-set",
        )
    return _clients["mistral"]


def _get_gemini():
    if "gemini" not in _clients:
        _clients["gemini"] = GeminiCompatClient(
            api_key=settings.gemini_api_key or "not-set",
        )
    return _clients["gemini"]


def _get_openrouter():
    if "openrouter" not in _clients:
        _clients["openrouter"] = AsyncOpenAI(
            api_key=settings.openrouter_api_key or "not-set",
            base_url=settings.openrouter_base_url,
        )
    return _clients["openrouter"]


def _resolve_provider(bot_name: str) -> str:
    """Pick provider from BOT_MODEL_MAP first, fall back to BOT_MODEL_MAP_SUBAGENTS."""
    if bot_name in BOT_MODEL_MAP:
        return BOT_MODEL_MAP[bot_name]
    if bot_name in BOT_MODEL_MAP_SUBAGENTS:
        return BOT_MODEL_MAP_SUBAGENTS[bot_name]
    return "mistral"


def get_model_for_bot(bot_name: str) -> OpenAIChatCompletionsModel:
    """Return the appropriate model for a bot."""
    provider = _resolve_provider(bot_name)

    if provider == "gemini":
        return OpenAIChatCompletionsModel(model=settings.gemini_model_id, openai_client=_get_gemini())
    if provider == "openrouter":
        return OpenAIChatCompletionsModel(model=settings.openrouter_model_id, openai_client=_get_openrouter())
    # default: mistral
    return OpenAIChatCompletionsModel(model=settings.mistral_model_id, openai_client=_get_mistral())


def get_openrouter_extra_body(reasoning_effort: str | None = "__unset__") -> dict:
    """Provider routing payload for OpenRouter requests. Pinned to verified
    tool_choice='required' enforcers. Order = priority; allow_fallbacks lets OpenRouter
    spill to the next if the top one is down.

    reasoning_effort: optional override. Pass "low" / "medium" / "high" to enable
    OpenRouter reasoning at that effort. Pass None to explicitly disable. Default
    ("__unset__") preserves legacy behavior (no reasoning key sent).
    """
    body: dict = {
        "provider": {
            "order": settings.openrouter_provider_order,
            "allow_fallbacks": True,
        }
    }
    if reasoning_effort != "__unset__":
        if reasoning_effort is None:
            body["reasoning"] = {"enabled": False}
        else:
            body["reasoning"] = {"effort": reasoning_effort}
    return body
