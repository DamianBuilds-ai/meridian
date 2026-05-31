# Meridian

A self-hostable, containerised multi-bot LLM agent framework for Telegram.

Each bot is an independent LLM agent with its own system prompt, toolset, and Docker
container. All bots share a single codebase and a single Dockerfile - the `BOT_NAME`
environment variable at runtime determines which agent loads.

## What Meridian provides

- **Multi-provider model routing** - OpenRouter (with provider order pinned for
  `tool_choice="required"` enforcement), Mistral, Gemini, OpenAI, Anthropic, Groq, and
  Ollama for local inference. Each bot routes to its own provider via `BOT_MODEL_MAP`
  in `src/config.py`.
- **Mandatory grounded tool-calls** - every bot system prompt enforces tool-first answers.
  The framework ships with the `AGGREGATE_GUARD_BOTS` mechanism to strip freelanced
  aggregate responses when a tool is expected.
- **Lazy bot registry** - bots are loaded on first use with per-bot error isolation. A
  broken agent import does not crash the other bots.
- **Sub-agent delegation** - bots can invoke specialist sub-agents as tools using the
  `Runner.run()` pattern (see the ContentPipelineBot and CoachBot examples).
- **SQLite session history** - conversation context persists across Telegram messages in
  a per-bot SQLite file mounted on a named Docker volume.
- **Langfuse tracing** - set `LANGFUSE_*` env vars to enable end-to-end LLM observability.
- **Docker Compose deploy** - one `docker compose up` starts the full fleet. Each bot runs
  in its own container; shared services (Redis, optional Ollama) run as siblings.

## Example Bots

The repo ships with seven worked examples. These are templates demonstrating different
framework patterns - adapt them or replace them with your own bots.

| Bot | Package | What it demonstrates |
|-----|---------|----------------------|
| **PipelineBot** | `src/pipelinebot/` | Mandatory tool-call grounding, fuzzy contact matching, two-phase delete confirmation in an outbound sales CRM assistant |
| **CreatorOps** | `src/creatorops/` | Cross-dataset set-intersection and a sub-LLM-as-a-tool pattern; unifies a contact list, content calendar, and subscriber list into one Telegram surface |
| **Lighthouse** | `src/lighthouse/` | Long-term SQLite memory, system-wide health aggregation, and cross-session relay - an ambient meta-layer bot that reports on your whole automation stack |
| **ContentPipelineBot** | `src/contentpipelinebot/` | Hub-and-spoke sub-agent delegation: one hub agent routes tasks to six specialist sub-agents exposed as tools (agent-as-a-tool pattern) |
| **ShiftBot** | `src/shiftbot/` | Upstream OCR handoff, write-time enrichment, and multi-user data isolation in a mobile-first gig earnings logger |
| **CoachBot** | `src/coachbot/` | Orchestrator-only router: tool_choice=required, no inline answers, write boundary enforced via three specialist sub-agents for a generic activity/skill practice domain |
| **Aria** | `src/aria/` | Mandatory warm-start memory hydration, free-slot scheduling, and generic webhook-based workflow triggering in a persistent personal assistant |

> These are worked examples - adapt or replace them with your own bots. The patterns
> they demonstrate (grounded tool-calls, sub-agent delegation, warm-start hydration,
> SQLite persistence, webhook triggers) are the reusable parts.

## Quickstart

```bash
# 1. Clone
git clone <repo-url> meridian && cd meridian

# 2. Configure
cp .env.example .env
# Edit .env - at minimum set OPENROUTER_API_KEY (or MISTRAL_API_KEY)
# and one TELEGRAM_BOT_TOKEN_* for the bot you want to run.

# 3. Start all example bots
docker compose up -d --build

# 4. Or start a single bot
docker compose up -d --build bot-pipelinebot
```

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- At least one LLM API key (OpenRouter or Mistral)
- One Telegram bot token per bot (create via @BotFather)

## Environment Variables

Copy `.env.example` to `.env`. Full variable list with descriptions is in `.env.example`.
Minimum viable set to run one bot:

```bash
OPENROUTER_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN_PIPELINEBOT=your_token_here
ALLOWED_USERS=your_telegram_user_id
MERIDIAN_DB_PATH=./data/meridian.db
```

## Model Routing

Provider selection lives in `src/config.py` (`BOT_MODEL_MAP`). Default routing for
OpenRouter pins the provider order to verified `tool_choice="required"` enforcers:

```
Together -> Fireworks -> SambaNova -> Cerebras
```

To route a bot to Mistral instead, set its value to `"mistral"` in `BOT_MODEL_MAP`.
To use a local Ollama model, set `OLLAMA_URL` in `.env` and set the bot to `"ollama"`.

## Self-Hosted Inference

The framework supports Ollama for local model inference. Set `OLLAMA_URL=http://ollama:11434`
in `.env`, uncomment the `ollama` service in `docker-compose.yml`, and update `BOT_MODEL_MAP`
to route the desired bots to `"ollama"`.

## Observability

Langfuse traces all LLM calls. Set `LANGFUSE_*` env vars to enable. The openinference
instrumentation wraps the OpenAI Agents SDK automatically - no code changes required.

## Project Structure

```
src/
  main.py                  - entry point
  config.py                - all env vars + per-bot model routing
  agents_registry.py       - lazy bot registry (add your bots here)
  handlers.py              - aiogram message routing
  session.py               - SQLite conversation history
  bot_application.py       - Burr state machine wrapper + aggregate guard
  shared/                  - shared utilities (model factory, Telegram helpers, etc.)
  pipelinebot/             - example: CRM action queue bot
  creatorops/              - example: creator operations hub
  lighthouse/              - example: ambient stack-monitor bot
  contentpipelinebot/      - example: hub-and-spoke sub-agent content pipeline
  shiftbot/                - example: gig earnings logger
  coachbot/                - example: orchestrator-only router to sub-agents
  aria/                    - example: persistent personal assistant with webhooks

docs/
  architecture.md          - end-to-end framework flow and patterns
  adding-a-bot.md          - step-by-step guide to adding your own bot
  deploy.md                - full deployment instructions
  PROMPTING.md             - system prompt guidelines
```

## Adding a Bot

See `docs/adding-a-bot.md` for the full step-by-step guide.

## License

Apache-2.0 - Damian Yazbeck
