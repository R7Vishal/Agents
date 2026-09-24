# Local Model Routing Strategy (Abstraction Only)

This project currently does **not** integrate with any LLM runtime.

No model is installed or invoked by default.

The reasoning layer is implemented as an abstraction for future integration with local or cloud providers.

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
- `src/coding_agent/presentation/web_app.py`
  - `POST /api/reasoning/route` for route inspection (no model invocation)
- `src/coding_agent/composition.py`
  - default local-first routing policy + null provider wiring

## Routing policy

Current defaults are tuned for local-first operation:

- Cloud fallback disabled
- Preferred context budget around 12K
- Maximum routed context budget 16K

Heuristic path:

- EASY -> 3B profile
- MEDIUM -> 7B profile
- HARD -> 7B profile (local-only mode) unless cloud fallback is enabled later

## Why this approach

- Keeps current application lightweight and deterministic
- Avoids adding inference/runtime dependencies before needed
- Preserves a clean plug-in point for Ollama/Azure/OpenAI integration later

## Integration path (future)

1. Add concrete provider class implementing `LLMProvider`
2. Register provider with `LLMGateway.register_provider(model_key, provider)`
3. Keep existing orchestration and UI unchanged

No architectural rewrites are required when providers are introduced.

## Mandatory checks before enabling real providers

1. Complete structured code-search adapters (`CodeSearchPort`)
2. Add structured edit/rollback engine (`CodeEditingEnginePort`)
3. Enforce containerized sandbox profile for command execution
4. Add policy + approval gates for high-impact actions
5. Add provider contract tests and fallback behavior tests
