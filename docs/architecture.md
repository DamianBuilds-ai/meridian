# Meridian Architecture

## Overview

Meridian is a self-hostable, containerised multi-bot LLM agent framework for Telegram.
Each bot is an independent LLM agent with its own system prompt, toolset, and Docker
container. All bots share a single codebase and Dockerfile - the `BOT_NAME` env var
at runtime selects which agent loads.

## Component Map

```
                          Telegram API
                               |
                    +----------+----------+
                    |  meridian-gateway   |
                    | (hub, health check, |
                    |  shared endpoints)  |
                    +----------+----------+
                               |
         +----------+----------+----------+----------+
         |          |          |          |          |
    bot-pipelinebot  bot-creatorops  bot-lighthouse  ... your bots

Shared services:
  bot-redis      - session cache + rate limiter
  searxng        - self-hosted web search (optional)
  langfuse        - LLM observability (optional, external or self-hosted)
  ollama          - local model inference (optional, uncomment in docker-compose)
```

## End-to-End Request Flow

```
User sends Telegram message
        |
        v
  aiogram handler (src/handlers.py)
        |
        | - loads session history from SQLite (src/session.py)
        | - calls get_agent_for_bot(bot_name) (src/agents_registry.py)
        v
  Lazy registry: first call imports src/{bot}/agent.py, caches the Agent object
        |
        v
  BurrBotApplication.run_turn() (src/bot_application.py)
        |
        | - builds message list: system + session history + new user message
        | - calls Runner.run(starting_agent, input=messages)
        v
  OpenAI Agents SDK runner
        |
        | - sends to LLM via model_factory (config.BOT_MODEL_MAP -> provider)
        | - LLM responds with a tool_call (tool_choice="required" enforced)
        v
  @function_tool execution
        |
        | - reads/writes SQLite, calls external APIs, or invokes a sub-agent
        | - returns structured result string
        v
  Runner continues: LLM formats final reply from tool output
        |
        v
  Aggregate guard (optional): strips freelanced totals on opt-in bots
        |
        v
  aiogram sends reply to Telegram (HTML parse mode)
        |
        v
  Session history appended to SQLite
```

## Mandatory Grounded Tool-Calls

Every bot system prompt enforces tool-first answers via two mechanisms:

1. `ModelSettings(tool_choice="required")` in the Agent definition - instructs the
   LLM to always call a tool rather than reply freehand.
2. System prompt rules that name which tool to call for each user intent.

The `AGGREGATE_GUARD_BOTS` set in `src/config.py` activates an optional post-processing
step that strips freelanced aggregate phrases from replies when no aggregate tool fired.
Add your bot to this set if it has tools that produce counts or totals.

## Sub-Agent Delegation Pattern

A bot can invoke specialist sub-agents as tools. The sub-agent is NOT registered in
`agents_registry.py` because it owns no Telegram token - it is imported lazily inside
the tool function.

```python
# src/mybot/tools/invoke_specialist.py
from agents import function_tool, Runner

@function_tool
async def invoke_specialist(text: str) -> str:
    """Route this task to the specialist sub-agent."""
    from mybot.subagents.specialist_agent import specialist_agent
    result = await Runner.run(starting_agent=specialist_agent, input=text)
    return result.final_output or "(no output)"
```

The hub agent calls `invoke_specialist` as a regular tool. The sub-agent runs
in-process with its own model settings and system prompt. This is the
hub-and-spoke pattern demonstrated by ContentPipelineBot and CoachBot.

**Sub-agent model routing**: sub-agent models are listed separately in
`BOT_MODEL_MAP_SUBAGENTS` in `src/config.py`, allowing lighter/cheaper models
for specialist workers.

## Lazy Bot Registry

`src/agents_registry.py` maps bot names to Python module paths. Agents are
loaded on first use via `__import__`. A failed import is logged but does not
crash the other bots - each bot is isolated.

Single-bot mode: set `BOT_NAME` in the container environment to load only one agent.
This is how Docker Compose runs each container - one container, one bot.

## Session Storage

Each bot container maintains a SQLite file at `/app/data/meridian.db` (path
configurable via `MERIDIAN_DB_PATH`). The named Docker volume (`data-{botname}`)
persists this across container restarts. Max session length and TTL are
configurable via `SESSION_TIMEOUT_S`.

For conversation history, `src/session.py` reads and writes to SQLite per user
and per bot, returning the message list in OpenAI message format.

## Model Routing

Model selection is centralised in `src/config.py` (`BOT_MODEL_MAP`) and
`src/shared/model_factory.py`. No bot hard-codes a model name - they call
`get_model_for_bot("botname")` which dispatches to the right client.

Provider order for OpenRouter is pinned to verified `tool_choice="required"`
enforcers: Together -> Fireworks -> SambaNova -> Cerebras.
Groq and Novita are excluded because they silently degrade tool_choice.

Supported providers: `"openrouter"`, `"mistral"`, `"ollama"`, `"openai"`, `"anthropic"`.

## Observability

Langfuse (self-hosted or cloud) traces all LLM calls. The openinference
instrumentation package wraps the OpenAI Agents SDK automatically - set
`LANGFUSE_*` env vars to enable. No bot code changes are required.

## Example Bot Roster

| Bot | Package | Pattern demonstrated |
|-----|---------|----------------------|
| PipelineBot | `src/pipelinebot/` | Grounded tool-calls, two-phase delete, contact matching |
| CreatorOps | `src/creatorops/` | Cross-dataset intersection, sub-LLM-as-a-tool |
| Lighthouse | `src/lighthouse/` | Long-term SQLite memory, health aggregation |
| ContentPipelineBot | `src/contentpipelinebot/` | Hub-and-spoke sub-agent delegation |
| ShiftBot | `src/shiftbot/` | OCR handoff, multi-user data isolation |
| CoachBot | `src/coachbot/` | Orchestrator-only router, write boundary |
| Aria | `src/aria/` | Warm-start hydration, scheduling, webhook trigger |

## Adding a Bot

See `docs/adding-a-bot.md` for the full step-by-step guide.

Quick summary:
1. Create `src/{botname}/agent.py` with a `{botname}_agent = Agent(...)` export
2. Create `src/{botname}/tools/__init__.py` with `ALL_TOOLS = [...]`
3. Create tool modules under `src/{botname}/tools/` (one `@function_tool` per file)
4. Add `"{botname}": "{botname}.agent"` to `ALL_AGENTS` in `agents_registry.py`
5. Add `telegram_bot_token_{botname}: str = ""` to `Settings` in `config.py`
6. Add provider to `BOT_MODEL_MAP` in `config.py`
7. Add credential check to `REQUIRED_CREDENTIALS` in `config.py`
8. Add a container block in `docker-compose.yml` and a named volume
