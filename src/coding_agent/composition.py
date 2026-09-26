from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .layers.mapping import LayerMapping, current_layer_mappings
from .retrieval import LocalCodeSearchAdapter
from .editing import StructuredEditor
from .orchestration.agent import CodingAgent
from .presentation.chat_service import CopilotChatService
from .reasoning import (
    HardwareProfile,
    LLMGateway,
    LMStudioProvider,
    ModelRouter,
    NullLLMProvider,
    RoutingPolicy,
)


@dataclass(frozen=True)
class LayeredAgentComponents:
    ui: str
    orchestrator: str
    reasoning: str
    repository_understanding: str
    code_search: str
    planning: str
    tool_calling: str
    code_editing: str
    sandbox_execution: str
    test_validation: str
    memory_context: str
    security_governance: str
    observability: str


@dataclass(frozen=True)
class LayeredAgentRuntime:
    project_root: Path
    orchestrator: CodingAgent
    chat_service: CopilotChatService
    model_router: ModelRouter
    llm_gateway: LLMGateway
    code_search: LocalCodeSearchAdapter
    code_editor: StructuredEditor
    layer_mappings: list[LayerMapping]
    components: LayeredAgentComponents


def build_default_runtime(project_root: Path) -> LayeredAgentRuntime:
    model_router = ModelRouter(
        hardware=HardwareProfile(vram_gb=8.0, system_ram_gb=12.0, cpu="Intel Core i7"),
        policy=RoutingPolicy(
            preferred_context_tokens=12000,
            max_context_tokens=16000,
            allow_cloud_fallback=False,
        ),
    )

    llm_gateway = LLMGateway(default_provider=NullLLMProvider())

    lmstudio_provider = LMStudioProvider()

    llm_gateway.register_provider(
        "qwen2.5-coder-3b-q4",
        lmstudio_provider,
    )

    llm_gateway.register_provider(
        "qwen2.5-coder-7b-q4",
        lmstudio_provider,
    )

    return LayeredAgentRuntime(
        project_root=project_root,
        orchestrator=CodingAgent(project_root),
        chat_service=CopilotChatService(),
        model_router=model_router,
        llm_gateway=llm_gateway,
        code_search=LocalCodeSearchAdapter(project_root),
        code_editor=StructuredEditor(project_root),
        layer_mappings=current_layer_mappings(),
        components=LayeredAgentComponents(
            ui="web_app.py + templates/index.html",
            orchestrator="agent.py::CodingAgent",
            reasoning="reasoning/ (ModelRouter + LLMGateway + LMStudioProvider)",
            repository_understanding="repo_intel.py",
            code_search="retrieval/adapters.py::LocalCodeSearchAdapter",
            planning="planner.py",
            tool_calling="command_runner.py + web_app dispatch",
            code_editing="editing/structured_editor.py::StructuredEditor",
            sandbox_execution="command_runner.py + safety.py + approval.py",
            test_validation="verifier.py + executor.py + validation_pipeline.py",
            memory_context="state_store.py + chat_service.py",
            security_governance="safety.py + integrity.py + lifecycle.py",
            observability="observability.py::JsonlLogger",
        ),
    )
