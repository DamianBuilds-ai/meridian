# Changelog

Notable changes to Meridian. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 2026-06-01

### Added
- Restored the Ollama provider branch in `src/shared/model_factory.py`, with an `ollama_model_id` setting (default `llama3`), so a bot routed to `ollama` uses the local self-hosted endpoint instead of silently falling back to Mistral. Ollama stays off by default in `BOT_MODEL_MAP`; it runs on CPU and is slower than the hosted providers, so it is opt-in via `OLLAMA_URL`.

### Changed
- Restyled the README architecture diagrams in the Meridian brand (stone and gold) and made them easier to read: the message-flow sequence now uses five lifelines with the registry, `tool_choice`, router and Langfuse steps shown as notes; the multi-provider routing diagram is a single-row fail-chain; the bot registry is a left-to-right tree.

### Fixed
- Added the missing `gemini` entry to the provider-list comment in `src/config.py`.

## 2026-05-31

### Added
- `## Architecture` section in the README with three Mermaid diagrams: a message-flow sequence diagram (mandatory `tool_choice=required` grounding, with the Langfuse trace shown as a non-blocking side effect), a multi-provider routing and fallback flowchart (the pinned OpenRouter order Together, Fireworks, SambaNova, Cerebras, with a bot-level fallback to Mistral or local Ollama), and a bot-registry graph of all seven example bots, showing the ContentPipelineBot and CoachBot hub-and-spoke sub-agent branches plus the CreatorOps sub-LLM reply drafter. The diagrams are committed as Mermaid fenced blocks and render natively on GitHub, so there is nothing to build or host.
- Badge row in the README (Apache-2.0, Python 3.12, aiogram, Docker Compose, Langfuse).

### Changed
- Corrected the provider list in the README. The wired LLM routes are OpenRouter, Mistral and Gemini, plus Ollama for local inference (per `src/shared/model_factory.py`). Groq was removed from the LLM list; it is used only for voice transcription via Whisper, not chat routing. OpenAI and Anthropic were removed; they have config keys but no route in the model factory.
- Corrected the ContentPipelineBot sub-agent count in the README from six to four, matching the four modules shipped under `src/contentpipelinebot/subagents/`.
- Clarified sub-agent model routing in `docs/architecture.md` to document how `BOT_MODEL_MAP_SUBAGENTS` is keyed.

### Fixed
- `BOT_MODEL_MAP_SUBAGENTS` keys in `src/config.py` never matched at runtime. The keys were prefixed (for example `contentpipelinebot_outliner`), but every sub-agent looks itself up by a bare name, for example `get_model_for_bot("outliner")`, so no key ever matched and all sub-agents silently fell through to the default model. The map is now keyed by the exact lookup names (`outliner`, `chapter_marker`, `retention_analyzer`, `seo_describer`, and the CreatorOps `creatorops_drafter` sub-LLM). Three stale keys with no matching module (`description_seo`, `hook_forge`, `script_outliner`) were removed, and the three `coachbot_*` keys were removed because CoachBot sub-agents look up the parent `coachbot` name and inherit its route by design. Every entry still resolves to the same provider as before, so model routing is unchanged; the map is simply live and honest now instead of dead.
