"""
Agent registry - maps bot names to Agent objects.

Each bot gets its own Agent with specific tools and system prompt.
Agents are lazy-loaded on first use with per-bot error isolation:
if one bot's agent.py has an import error, all other bots still work.

In single-bot mode (BOT_NAME env var), only the named bot is loaded.

Add your own bots under src/ following the pattern:
  src/{bot_name}/__init__.py
  src/{bot_name}/agent.py  (must export `{bot_name}_agent`)
  src/{bot_name}/tools/    (optional tool modules)

Then register the bot in ALL_AGENTS below.
"""

import logging
import os

log = logging.getLogger(__name__)

_AGENTS: dict = {}
_loaded = False

BOT_NAME = os.environ.get("BOT_NAME", "").strip().lower()

# Register your bots here. Key = bot name, value = Python module path.
# The module must export an attribute named `{bot_name}_agent`.
ALL_AGENTS: dict[str, str] = {
    # Example bots - adapt or replace with your own.
    # Each key is the bot name (matches BOT_NAME env var and Telegram token suffix).
    # Each value is the Python module path relative to src/.
    "pipelinebot": "pipelinebot.agent",
    "creatorops": "creatorops.agent",
    "lighthouse": "lighthouse.agent",
    "contentpipelinebot": "contentpipelinebot.agent",
    "shiftbot": "shiftbot.agent",
    "coachbot": "coachbot.agent",
    "aria": "aria.agent",
}


def _load_agents():
    """Lazy-load agents with per-bot error isolation."""
    global _loaded
    _loaded = True

    if BOT_NAME:
        # Single-bot mode - load only the named bot
        agents_to_load = {BOT_NAME: ALL_AGENTS.get(BOT_NAME)}
        if not agents_to_load[BOT_NAME]:
            log.error(f"Unknown bot in BOT_NAME: {BOT_NAME}")
            return
    else:
        agents_to_load = ALL_AGENTS

    for name, module_path in agents_to_load.items():
        try:
            module = __import__(module_path, fromlist=["agent"])
            agent_attr = f"{name.replace('-', '_')}_agent"
            if hasattr(module, agent_attr):
                _AGENTS[name] = getattr(module, agent_attr)
                log.info(f"Loaded agent: {name}")
            else:
                log.warning(f"Agent module {module_path} has no '{agent_attr}' attribute")
        except Exception as e:
            log.error(f"Failed to load {name} agent: {e}")
            # Continue loading other agents - don't crash everything


def get_agent_for_bot(bot_name: str):
    """Get the agent for a given bot name."""
    if not _loaded:
        _load_agents()
    return _AGENTS.get(bot_name)
