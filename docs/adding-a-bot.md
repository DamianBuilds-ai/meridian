# Adding a Bot to Meridian

This guide walks through every step needed to add a new bot to the framework.
Use the example bots in `src/` as templates - each one demonstrates a different
pattern you can copy directly.

---

## Step 1 - Create the package

Create a directory for your bot under `src/`:

```
src/
  mybot/
    __init__.py
    agent.py
    tools/
      __init__.py
      my_tool.py
```

The `__init__.py` files can be empty. The package name must be lowercase and match
the `BOT_NAME` value you will set later.

---

## Step 2 - Define the agent

Create `src/mybot/agent.py`. The file must export a variable named `{botname}_agent`:

```python
from agents import Agent, ModelSettings
from mybot.tools import ALL_TOOLS
from shared.model_factory import get_model_for_bot, get_openrouter_extra_body

SYSTEM_PROMPT = """You are MyBot, a ... assistant.

Telegram HTML ONLY: <b>bold</b>, <i>italic</i>, <code>mono</code>.
BANNED: **bold** *italic* `code` # headers.

CORE RULES:
- You MUST call a tool for every user request. Never answer from memory alone.
- [add your grounding rules here]
"""

mybot_agent = Agent(
    name="MyBot",
    instructions=SYSTEM_PROMPT,
    tools=ALL_TOOLS,
    model=get_model_for_bot("mybot"),
    model_settings=ModelSettings(
        temperature=0.2,
        tool_choice="required",
        extra_body=get_openrouter_extra_body(),
    ),
)
```

Key points:
- `tool_choice="required"` enforces grounded tool-calls on every turn.
- The system prompt should spell out which tool to call for each user intent.
- Keep the Telegram HTML formatting rules - the framework sends HTML parse mode.

See `src/pipelinebot/agent.py` for a minimal grounded-tool-call example.
See `src/contentpipelinebot/agent.py` for a hub-and-spoke sub-agent example.
See `src/coachbot/agent.py` for an orchestrator-only router example.

---

## Step 3 - Add tools

Each tool is a Python function decorated with `@function_tool` from the `agents` SDK.

Create `src/mybot/tools/my_tool.py`:

```python
from agents import function_tool

@function_tool
async def my_tool(query: str) -> str:
    """Fetch data for the given query and return a formatted result."""
    # Your logic here. Use SQLite, an HTTP API, or a stub.
    # TODO: replace this stub with a real implementation.
    return f"[stub] result for: {query}"
```

Then collect all tools in `src/mybot/tools/__init__.py`:

```python
from mybot.tools.my_tool import my_tool

ALL_TOOLS = [my_tool]
```

Guidelines:
- One tool per file keeps the code easy to read and test.
- Return Telegram-safe HTML strings (avoid raw markdown).
- For SQLite persistence, see `src/pipelinebot/_db.py` or `src/aria/db.py` as patterns.
- For a sub-agent-as-a-tool, see `src/contentpipelinebot/tools/` or `src/coachbot/tools/`.
- Where a real third-party account would be needed, return a clear stub with a
  `TODO` comment pointing to the relevant API documentation.

---

## Step 4 - Register the bot

Open `src/agents_registry.py` and add your bot to `ALL_AGENTS`:

```python
ALL_AGENTS: dict[str, str] = {
    # ... existing bots ...
    "mybot": "mybot.agent",
}
```

The key is the bot name (must match `BOT_NAME` in docker-compose and the Telegram
token suffix). The value is the Python module path relative to `src/`.

---

## Step 5 - Set model and Telegram token in config

Open `src/config.py` and make three additions:

**a) Telegram token field** (in the `Settings` class):

```python
telegram_bot_token_mybot: str = ""
```

**b) Model routing** (in `BOT_MODEL_MAP`):

```python
"mybot": "openrouter",  # or "mistral" or "ollama"
```

**c) Required credentials** (in `REQUIRED_CREDENTIALS`):

```python
"mybot": ["openrouter_api_key"],
```

---

## Step 6 - Add the token to .env

Add to your `.env` file:

```bash
TELEGRAM_BOT_TOKEN_MYBOT=your_bot_token_from_botfather
```

---

## Step 7 - Add a container in docker-compose.yml

Copy one of the existing service blocks and adjust:

```yaml
bot-mybot:
  <<: *bot-defaults
  container_name: bot-mybot
  environment:
    - BOT_NAME=mybot
    - TZ=UTC
  ports:
    - "127.0.0.1:8108:8090"  # pick a unique host port
  volumes:
    - data-mybot:/app/data
```

Also add the named volume at the bottom of `docker-compose.yml`:

```yaml
volumes:
  # ... existing volumes ...
  data-mybot:
```

---

## Step 8 - Start the bot

```bash
docker compose up -d --build bot-mybot
docker compose logs -f bot-mybot
```

---

## Patterns reference

| Pattern | Example bot | Key files |
|---------|------------|-----------|
| Grounded tool-calls (tool_choice=required) | PipelineBot | `src/pipelinebot/agent.py` |
| SQLite persistence | PipelineBot, Aria | `src/pipelinebot/_db.py`, `src/aria/db.py` |
| Sub-LLM-as-a-tool (hub-and-spoke) | ContentPipelineBot | `src/contentpipelinebot/tools/` |
| Orchestrator-only router | CoachBot | `src/coachbot/agent.py`, `src/coachbot/tools/` |
| Cross-dataset set-intersection | CreatorOps | `src/creatorops/tools/` |
| Long-term SQLite memory | Lighthouse | `src/lighthouse/_db.py` |
| Warm-start memory hydration | Aria | `src/aria/tools/warm_start.py` |
| Outbound webhook trigger | Aria | `src/aria/tools/trigger_workflow.py` |
| Multi-user data isolation | ShiftBot | `src/shiftbot/db.py` |
| Photo/OCR handoff | ShiftBot | `src/shiftbot/tools/` |

---

## Troubleshooting

**Agent import fails silently** - check `docker compose logs -f bot-mybot`. A missing
dependency or import error is logged but does not crash other bots.

**Tool never called** - verify `tool_choice="required"` is set in `ModelSettings` and
that your system prompt maps each user intent to a named tool.

**Token not picked up** - the env var name must be `TELEGRAM_BOT_TOKEN_{BOTNAME}` where
`{BOTNAME}` is the uppercased `BOT_NAME` value.
