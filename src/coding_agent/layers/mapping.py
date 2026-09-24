from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerMapping:
    layer_name: str
    current_module: str
    status: str
    integration_point: str


def current_layer_mappings() -> list[LayerMapping]:
    return [
        LayerMapping(
            layer_name="1. User Interface",
            current_module="coding_agent.web_app, coding_agent.templates.index",
            status="implemented",
            integration_point="Flask endpoints, async job polling, chat UI",
        ),
        LayerMapping(
            layer_name="2. Agent Orchestrator",
            current_module="coding_agent.agent.CodingAgent",
            status="implemented",
            integration_point="first_run_assessment, run_controlled_plan, rotate_checkpoint_key",
        ),
        LayerMapping(
            layer_name="3. LLM / Reasoning Engine",
            current_module="coding_agent.reasoning (ModelRouter + LLMGateway + NullLLMProvider)",
            status="implemented-abstraction",
            integration_point="Hardware-aware route selection + provider abstraction (no runtime provider integration)",
        ),
        LayerMapping(
            layer_name="4. Repository Understanding",
            current_module="coding_agent.repo_intel",
            status="implemented",
            integration_point="discover_repository metadata extraction",
        ),
        LayerMapping(
            layer_name="5. Code Search / RAG",
            current_module="coding_agent.retrieval.adapters::LocalCodeSearchAdapter",
            status="implemented-foundation",
            integration_point="symbol + semantic + dependency retrieval over workspace",
        ),
        LayerMapping(
            layer_name="6. Planning Engine",
            current_module="coding_agent.planner",
            status="implemented",
            integration_point="recommend_next_milestone",
        ),
        LayerMapping(
            layer_name="7. Tool / Function Calling",
            current_module="coding_agent.command_runner, coding_agent.web_app tool-like APIs",
            status="partial",
            integration_point="command execution, endpoint-dispatched actions",
        ),
        LayerMapping(
            layer_name="8. Code Editing Engine",
            current_module="coding_agent.editing.structured_editor::StructuredEditor",
            status="implemented-foundation",
            integration_point="replace/insert primitives with rollback checkpoints",
        ),
        LayerMapping(
            layer_name="9. Sandbox / Code Execution",
            current_module="coding_agent.command_runner",
            status="implemented-foundation",
            integration_point="allowlist + scoped writes + optional container profile + approval checks",
        ),
        LayerMapping(
            layer_name="10. Test & Validation Engine",
            current_module="coding_agent.verifier, coding_agent.executor",
            status="implemented-expanded",
            integration_point="baseline checks + repair loop + staged validation gates with deterministic retries",
        ),
        LayerMapping(
            layer_name="11. Memory / Context Management",
            current_module="coding_agent.state_store, coding_agent.chat_service",
            status="implemented",
            integration_point="run records/checkpoints + in-memory chat sessions",
        ),
        LayerMapping(
            layer_name="12. Security & Governance",
            current_module="coding_agent.safety, coding_agent.integrity, coding_agent.lifecycle",
            status="implemented",
            integration_point="blocked command policy, signed checkpoints, guarded state transitions",
        ),
    ]
