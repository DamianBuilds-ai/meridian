# Meridian Deploy Guide

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A Telegram bot token for each bot you want to run (get from @BotFather)
- At minimum: an OpenRouter API key and the Telegram token for your chosen bot

## Quickstart

```bash
# 1. Clone the repo
git clone <repo-url> meridian
cd meridian

# 2. Set up environment
cp .env.example .env
# Edit .env - fill in your tokens and API keys

# 3. Build and start the fleet
docker compose up -d --build

# 4. Check status
docker compose ps
docker compose logs -f meridian-gateway
```

## Single-Bot Mode (recommended for getting started)

Each container runs exactly one bot, controlled by the `BOT_NAME` env var.
To run just the example assistant bot:

```bash
docker compose up -d --build bot-assistant
docker compose logs -f bot-assistant
```

## Health Checks

Every bot container exposes a health endpoint at port 8090:

```bash
curl http://localhost:8101/health   # first bot (bot-assistant by default)
curl http://localhost:8102/health   # second bot
curl http://localhost:8090/health   # gateway
```

Port assignments are configured in `docker-compose.yml`. Add a new block
for each bot you create, incrementing the host port.

## External Networks

The compose file expects two external Docker networks to already exist:

```bash
docker network create shared
```

Langfuse: if you are not running Langfuse, comment out or remove
`langfuse_default` from the networks section and the bot defaults.

## Rebuilding a Single Bot

```bash
docker compose up -d --build bot-assistant
```

## Updating

```bash
git pull
docker compose up -d --build
```

## Enabling Ollama (Local Inference)

1. Uncomment the `ollama` service in `docker-compose.yml`
2. Add `- ollama-data:` to the `volumes:` section
3. Add `ollama:` to the `networks:` of each bot that should use local inference
4. Set `OLLAMA_URL=http://ollama:11434` in `.env`
5. Update `BOT_MODEL_MAP` in `src/config.py` to route desired bots to `"ollama"`
6. Add an `"ollama"` branch back to `src/shared/model_factory.py`

```bash
docker compose up -d --build ollama
docker compose exec ollama ollama pull <your-model>
# or use your own Modelfile:
docker compose cp /path/to/Modelfile ollama:/tmp/Modelfile
docker compose exec ollama ollama create my-model -f /tmp/Modelfile
```

## Logs

```bash
docker compose logs -f                        # all services
docker compose logs -f bot-assistant          # one bot
docker compose logs --tail=100 bot-assistant  # last 100 lines
```

## Stopping

```bash
docker compose down          # stop, keep volumes
docker compose down -v       # stop AND remove volumes (session data lost)
```
