"""
Burr state machine wrapper for Meridian bots.

Wraps the OpenAI Agents SDK Runner.run() in a Burr Application,
giving us: tracking UI, time-travel debugging, state persistence,
and step-by-step inspection of every conversation.

Each (bot_name, user_id) pair gets its own Application instance.
The tracking UI shows one project per bot, one app per user.
"""

import logging
import asyncio
import re
from burr.core import action, State, ApplicationBuilder
from burr.tracking import LocalTrackingClient
from agents import Runner
from agents_registry import get_agent_for_bot
from session import get_session
from shared.emit import emit_event

log = logging.getLogger("burr")

BURR_DATA_DIR = "/app/data/burr"

# Patterns that look like a fabricated aggregate. Phrase-level (not line-level)
# to avoid eating the legitimate log confirmation when the aggregate shares a line.
_AGG_PATTERNS = [
    re.compile(r"(?im)\bTotal\s+(?:today|yesterday|this\s+week|this\s+month|this\s+year)\b[^.\n]*[.!?]?"),
    re.compile(r"(?im)\bacross\s+\d+\s+sessions?\b[^.\n]*[.!?]?"),
    re.compile(r"(?im)\b(?:running|cumulative)\s+total\b[^.\n]*[.!?]?"),
    re.compile(r"(?im)\byou(?:'ve|\s+have)\s+(?:now\s+)?done\s+\d+[^.\n]*\btotal\b[^.\n]*[.!?]?"),
    re.compile(r"(?im)\bsession\s+count\s*:[^\n]*"),
]


def _strip_freelance_aggregates(reply: str, tool_names_called: set[str]) -> tuple[str, bool]:
    """
    Strip hallucinated aggregate phrases from a bot reply.
    Returns (cleaned_reply, was_stripped).
    If a real summary tool fired this turn, returns reply unchanged.
    """
    from config import AGGREGATE_TOOL_NAMES
    if tool_names_called & AGGREGATE_TOOL_NAMES:
        return reply, False  # totals are real, leave alone

    cleaned = reply
    for pat in _AGG_PATTERNS:
        cleaned = pat.sub("", cleaned)
    # Collapse double-spaces left by phrase-level removals
    cleaned = re.sub(r"  +", " ", cleaned)
    # Collapse blank-line runs the strip may create
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, (cleaned != reply)


def _last_tool_output(result) -> str:
    """Return the last function_call_output string from a Runner result, if any.

    Tries result.raw_responses first (older SDK shape), then falls back to
    result.new_items where ToolCallOutputItem instances live in newer SDKs.
    """
    # Path 1: raw_responses[i].output[j] with type='function_call_output'
    for item in reversed(getattr(result, 'raw_responses', []) or []):
        for call in reversed(getattr(item, 'output', []) or []):
            if hasattr(call, 'type') and call.type == 'function_call_output':
                out = getattr(call, 'output', '') or ''
                return str(out).strip()

    # Path 2: new_items contains ToolCallOutputItem instances
    for item in reversed(getattr(result, 'new_items', []) or []):
        # Detect by class name to avoid hard import dependency
        if type(item).__name__ == 'ToolCallOutputItem':
            # ToolCallOutputItem has .output (str) attribute
            out = getattr(item, 'output', '') or ''
            if out:
                return str(out).strip()
            # Fallback: dig into raw_item
            raw = getattr(item, 'raw_item', None)
            if raw is not None:
                out = getattr(raw, 'output', '') or (raw.get('output', '') if isinstance(raw, dict) else '')
                if out:
                    return str(out).strip()
    return ""


@action(reads=[], writes=["prompt"])
def receive_message(state: State, prompt: str) -> State:
    """Records incoming user message. Sync - no I/O."""
    return state.update(prompt=prompt)


@action(reads=["prompt"], writes=["response"])
async def run_agent(state: State, agent, openai_session) -> State:
    """Calls the OpenAI Agents SDK Runner - the actual agent work."""
    from agents.exceptions import MaxTurnsExceeded

    # Get bot name from agent for event emission
    bot_name = getattr(agent, 'name', '').lower() or 'unknown'

    try:
        result = await Runner.run(
            agent,
            input=state["prompt"],
            session=openai_session,
            max_turns=5,
        )
        response_text = result.final_output or "Done."

        # Collect tool names called this turn (used by aggregate guard + emit)
        tool_names_called: set[str] = set()
        for item in getattr(result, 'raw_responses', []):
            for call in getattr(item, 'output', []):
                if hasattr(call, 'type') and call.type == 'function_call':
                    name = getattr(call, 'name', '?')
                    tool_names_called.add(name)
                    asyncio.create_task(emit_event(
                        bot_name, "tool_call",
                        tool=name,
                        preview=str(getattr(call, 'arguments', ''))[:100]
                    ))

        # Pre-send aggregate guard: strip freelanced totals on opt-in bots.
        from config import AGGREGATE_GUARD_BOTS
        if bot_name in AGGREGATE_GUARD_BOTS:
            original = response_text
            cleaned, stripped = _strip_freelance_aggregates(original, tool_names_called)
            if stripped:
                if not cleaned.strip():
                    tool_echo = _last_tool_output(result)
                    response_text = tool_echo or "Got it."
                    log.warning(
                        f"[{bot_name}] guard stripped reply to empty; falling back. "
                        f"original={original!r}"
                    )
                else:
                    response_text = cleaned
                    log.warning(f"[{bot_name}] stripped hallucinated aggregate from reply")
                asyncio.create_task(emit_event(
                    bot_name, "guard_strip",
                    preview="hallucinated_aggregate_stripped"
                ))

    except MaxTurnsExceeded:
        response_text = "I couldn't find a definitive answer. Try rephrasing, or ask me something more specific."
    except Exception as e:
        log.exception("Agent run failed")
        response_text = f"Error: {type(e).__name__}: {str(e)[:200]}"
        asyncio.create_task(emit_event(bot_name, "error", preview=str(e)[:100]))

    return state.update(response=response_text)


def build_app(bot_name: str, user_id: int):
    """Build a Burr application for one user conversation."""
    agent = get_agent_for_bot(bot_name)
    if not agent:
        return None

    openai_session = get_session(bot_name, user_id)
    tracker = LocalTrackingClient(project=bot_name, storage_dir=BURR_DATA_DIR)

    app_id = f"{bot_name}-{user_id}"

    return (
        ApplicationBuilder()
        .with_actions(
            receive_message,
            run_agent=run_agent.bind(agent=agent, openai_session=openai_session),
        )
        .with_transitions(
            ("receive_message", "run_agent"),
            ("run_agent", "receive_message"),
        )
        .with_tracker(tracker)
        .with_identifiers(
            app_id=app_id,
            partition_key=str(user_id),
        )
        .initialize_from(
            tracker,
            resume_at_next_action=True,
            default_state={"prompt": "", "response": ""},
            default_entrypoint="receive_message",
        )
        .build()
    )


# Cache apps per (bot, user) so we don't rebuild on every message
_app_cache: dict[str, object] = {}


def get_or_create_app(bot_name: str, user_id: int):
    """Get or create a Burr app for a bot+user combination."""
    key = f"{bot_name}:{user_id}"
    if key not in _app_cache:
        app = build_app(bot_name, user_id)
        if app:
            _app_cache[key] = app
    return _app_cache.get(key)


async def handle_message(bot_name: str, user_id: int, text: str) -> str:
    """Main entry point - called from handlers.py."""
    app = get_or_create_app(bot_name, user_id)
    if not app:
        return "This bot is not configured yet."

    # Run the state machine: receive_message -> run_agent
    _, _, state = await app.arun(
        halt_after=["run_agent"],
        inputs={"prompt": text},
    )
    return state["response"]
