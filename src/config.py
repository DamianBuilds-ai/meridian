"""
Configuration loaded from environment variables.
All secrets stay in .env - never hardcoded, never committed.

Self-hosted model path (Ollama) is supported via OLLAMA_URL env var.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenRouter (primary multi-provider inference router)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_id: str = "openai/gpt-4o-mini"
    openrouter_provider_order: list[str] = ["together", "fireworks", "sambanova", "cerebras"]

    # Mistral (fallback inference provider, default for lightweight bots)
    mistral_api_key: str = ""
    mistral_model_id: str = "mistral-small-latest"

    # Gemini (photo OCR, optional)
    gemini_api_key: str = ""
    gemini_model_id: str = "gemini-2.0-flash"

    # OpenAI direct (optional)
    openai_api_key: str = ""

    # Anthropic (optional)
    anthropic_api_key: str = ""

    # Groq (voice transcription, optional)
    groq_api_key: str = ""

    # SearXNG (self-hosted search, optional - runs as a Docker sibling)
    searxng_url: str = "http://searxng:8080"

    # Langfuse (observability, optional)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "http://langfuse-langfuse-web-1:3000"

    # Telegram bot tokens - one per example bot.
    # Add your own following the same naming convention:
    #   telegram_bot_token_{botname}: str = ""
    telegram_bot_token_pipelinebot: str = ""
    telegram_bot_token_creatorops: str = ""
    telegram_bot_token_lighthouse: str = ""
    telegram_bot_token_contentpipelinebot: str = ""
    telegram_bot_token_shiftbot: str = ""
    telegram_bot_token_coachbot: str = ""
    telegram_bot_token_aria: str = ""

    webhook_base_url: str = "https://api.example.com/webhook/bots"
    allowed_users: str = ""  # comma-separated Telegram user IDs

    # SQLite database path used by bots that persist data locally.
    # Inside Docker the default resolves to /app/data/meridian.db
    # (the data volume is mounted at /app/data per docker-compose.yml).
    meridian_db_path: str = "./data/meridian.db"

    # Aria: optional external automation webhook
    aria_webhook_url: str = ""
    aria_webhook_timeout: float = 8.0

    # Database (PostgreSQL session store - optional, only needed if you
    # replace the SQLite session backend with PostgreSQL).
    database_url: str = ""

    # Redis
    redis_url: str = "redis://bot-redis:6379/0"

    # Ollama (optional local model).
    # Uncomment the ollama service in docker-compose.yml to enable.
    ollama_url: str = ""

    # Table store (optional row-based external store).
    # Only needed if you use shared/tablestore.py in your own bots.
    # The example bots use SQLite and do not require these.
    table_store_url: str = ""
    table_store_token: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def allowed_user_ids(self) -> set[int]:
        if not self.allowed_users:
            return set()
        return {int(uid.strip()) for uid in self.allowed_users.split(",") if uid.strip()}


settings = Settings()


def _validate_database_url() -> None:
    """Optional guard: refuse to start if DATABASE_URL uses the example placeholder.

    Call this explicitly if your deployment uses PostgreSQL for session storage.
    The example bots use SQLite and do not require DATABASE_URL.
    """
    url = settings.database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file. "
            "See .env.example for the required format."
        )
    if "CHANGE_ME" in url:
        raise RuntimeError(
            "DATABASE_URL still contains the placeholder password 'CHANGE_ME'. "
            "Set a real password in DATABASE_URL in your .env file before running."
        )

# --- Per-bot model routing ---
# Each bot gets routed to one provider. Add your bots here.
# - "openrouter": OpenRouter aggregator
# - "mistral": Mistral (default for unlisted bots)
# - "ollama": local model (set OLLAMA_URL and uncomment ollama in docker-compose)
BOT_MODEL_MAP = {
    # Example bots. Change "openrouter"/"mistral"/"ollama" to re-route a bot.
    "pipelinebot": "openrouter",        # CRM action queue
    "creatorops": "openrouter",         # creator operations hub
    "lighthouse": "mistral",            # lightweight ambient monitor
    "contentpipelinebot": "openrouter", # hub + specialist sub-agents
    "shiftbot": "mistral",              # gig earnings logger (fast, cheap)
    "coachbot": "openrouter",           # activity router to sub-agents
    "aria": "openrouter",               # persistent personal assistant
}

# Sub-agents dispatched as tools - route to a separate provider if desired.
BOT_MODEL_MAP_SUBAGENTS: dict[str, str] = {
    "contentpipelinebot_outliner": "mistral",
    "contentpipelinebot_chapter_marker": "mistral",
    "contentpipelinebot_description_seo": "mistral",
    "contentpipelinebot_hook_forge": "mistral",
    "contentpipelinebot_retention_analyzer": "mistral",
    "contentpipelinebot_script_outliner": "mistral",
    "coachbot_session_logger": "mistral",
    "coachbot_progress_tracker": "mistral",
    "coachbot_goal_planner": "mistral",
}

# --- Credential validation per bot ---
# Bots with missing required credentials are skipped at startup.
REQUIRED_CREDENTIALS: dict[str, list[str]] = {
    "pipelinebot": ["openrouter_api_key"],
    "creatorops": ["openrouter_api_key"],
    "lighthouse": ["mistral_api_key"],
    "contentpipelinebot": ["openrouter_api_key"],
    "shiftbot": ["mistral_api_key"],
    "coachbot": ["openrouter_api_key"],
    "aria": ["openrouter_api_key"],
}


def check_bot_credentials(bot_name: str) -> list[str]:
    """Return list of missing required credentials for a bot. Empty = all good."""
    required = REQUIRED_CREDENTIALS.get(bot_name, [])
    return [k for k in required if not getattr(settings, k, "")]


# --- Aggregate guard (anti-hallucination) ---
# Add bot names here to strip freelanced aggregate phrases from replies.
AGGREGATE_GUARD_BOTS: set[str] = set()

# Tool names that genuinely produce aggregate output - guard skips stripping
# when one of these fired this turn.
AGGREGATE_TOOL_NAMES: set[str] = set()
