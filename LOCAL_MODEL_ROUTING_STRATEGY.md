# Local Model Routing Strategy (Policy-Gated Runtime Integration)

This project keeps a **safe default** reasoning configuration:

- No external provider is invoked by default (`NullLLMProvider`)
- Optional provider-backed inference is supported via environment configuration
- Routing and telemetry are always available for observability

## Hardware assumptions

- GPU VRAM: 8 GB
- System RAM: 12 GB
- CPU: Intel Core i7

## Recommended model profiles (future integration)

- Fast local profile: `Qwen2.5-Coder-3B-Instruct Q4`
- Main local profile: `Qwen2.5-Coder-7B-Instruct Q4`
- Optional fallback profile: `Cloud LLM`

## Current implementation

- `src/coding_agent/reasoning/router.py`
  - `HeuristicTaskClassifier`
  - `ModelRouter`
- `src/coding_agent/reasoning/provider.py`
  - `LLMGateway`
  - `NullLLMProvider`
  - `OpenAICompatibleProvider` (optional)
- `src/coding_agent/presentation/web_app.py`
  - `POST /api/reasoning/route` for route inspection (no model invocation)
- `src/coding_agent/composition.py`
  - default local-first routing policy + optional provider registration

Runtime env toggles:

- `CODING_AGENT_ALLOW_CLOUD=true|false`
- `CODING_AGENT_LLM_PROVIDER=openai-compatible`
- `CODING_AGENT_LLM_BASE_URL=<provider-base-url>`
- `CODING_AGENT_LLM_API_KEY=<api-key>`
- `CODING_AGENT_LLM_MODEL=<model-id>`

## Routing policy

Current defaults are tuned for local-first operation:

- Cloud fallback disabled
- Preferred context budget around 12K
- Maximum routed context budget 16K

Heuristic path:

- EASY -> 3B profile
- MEDIUM -> 7B profile
- HARD -> 7B profile (local-only mode) unless cloud fallback is enabled later

Telemetry:

- Provider invocation audit events are captured (success/failure, tokens, latency)
- Available via `GET /api/reasoning/telemetry`

## Why this approach

- Keeps current application lightweight and deterministic
- Avoids adding inference/runtime dependencies before needed
- Preserves a clean plug-in point for Ollama/Azure/OpenAI integration later

## Integration path

1. Add concrete provider class implementing `LLMProvider`
2. Register provider with `LLMGateway.register_provider(model_key, provider)`
3. Keep existing orchestration and UI unchanged

The repository already includes step 1 and 2 for OpenAI-compatible APIs; additional providers can follow the same contract.

No architectural rewrites are required when providers are introduced.

## Mandatory checks before enabling real providers

1. Complete structured code-search adapters (`CodeSearchPort`)
2. Add structured edit/rollback engine (`CodeEditingEnginePort`)
3. Enforce containerized sandbox profile for command execution
4. Add policy + approval gates for high-impact actions
5. Add provider contract tests and fallback behavior tests
