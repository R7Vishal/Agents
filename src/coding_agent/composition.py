from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .layers.mapping import LayerMapping, current_layer_mappings
from .retrieval import LocalCodeSearchAdapter
from .editing import StructuredEditor
from .orchestration.agent import CodingAgent
from .presentation.chat_service import CopilotChatService
from .reasoning import HardwareProfile, LLMGateway, ModelRouter, NullLLMProvider, OpenAICompatibleProvider, RoutingPolicy
from .tools import AgentDoctor, CapabilityManager, SelfImprovementAdvisor, ToolRegistry, register_default_tools
from .tools.approval_tokens import ApprovalTokenManager
from .workspace_manager import WorkspaceManager


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
    workspace_manager: WorkspaceManager
    tool_registry: ToolRegistry
    approval_tokens: ApprovalTokenManager
    capability_manager: CapabilityManager
    doctor: AgentDoctor
    advisor: SelfImprovementAdvisor
    execution_mode: str
    layer_mappings: list[LayerMapping]
    components: LayeredAgentComponents


def build_default_runtime(project_root: Path) -> LayeredAgentRuntime:
    allow_cloud_fallback = str(os.getenv("CODING_AGENT_ALLOW_CLOUD", "false") or "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    model_router = ModelRouter(
        hardware=HardwareProfile(vram_gb=8.0, system_ram_gb=12.0, cpu="Intel Core i7"),
        policy=RoutingPolicy(
            preferred_context_tokens=12000,
            max_context_tokens=16000,
            allow_cloud_fallback=allow_cloud_fallback,
        ),
    )
    llm_gateway = LLMGateway(default_provider=NullLLMProvider())
    provider = OpenAICompatibleProvider.from_env()
    if provider is not None:
        llm_gateway.register_provider(model_router.cloud_fallback.key, provider)
        llm_gateway.register_provider(model_router.main_local.key, provider)
        llm_gateway.register_provider(model_router.fast_local.key, provider)

    workspace_manager = WorkspaceManager(project_root)
    tool_registry = ToolRegistry()
    execution_mode = str(os.getenv("CODING_AGENT_EXECUTION_MODE", "auto")).strip().lower() or "auto"
    approval_tokens = ApprovalTokenManager(project_root / ".agent_state")
    register_default_tools(
        tool_registry,
        workspace_manager,
        mode=execution_mode,
        approval_tokens=approval_tokens,
    )
    capability_manager = CapabilityManager(tool_registry)
    doctor = AgentDoctor(tool_registry, capability_manager, project_root)
    advisor = SelfImprovementAdvisor(capability_manager)
    chat_service = CopilotChatService(
        tool_registry=tool_registry,
        capability_manager=capability_manager,
        doctor=doctor,
        advisor=advisor,
        workspace_manager=workspace_manager,
    )

    return LayeredAgentRuntime(
        project_root=project_root,
        orchestrator=CodingAgent(project_root),
        chat_service=chat_service,
        model_router=model_router,
        llm_gateway=llm_gateway,
        code_search=LocalCodeSearchAdapter(project_root),
        code_editor=StructuredEditor(project_root),
        workspace_manager=workspace_manager,
        tool_registry=tool_registry,
        approval_tokens=approval_tokens,
        capability_manager=capability_manager,
        doctor=doctor,
        advisor=advisor,
        execution_mode=execution_mode,
        layer_mappings=current_layer_mappings(),
        components=LayeredAgentComponents(
            ui="web_app.py + templates/index.html",
            orchestrator="agent.py::CodingAgent",
            reasoning="reasoning/ (ModelRouter + LLMGateway + optional provider integration)",
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
