from pathlib import Path

from coding_agent.tools import AgentDoctor, CapabilityManager, ToolRegistry, register_default_tools
from coding_agent.workspace_manager import WorkspaceManager


def test_tool_registry_and_capabilities(tmp_path: Path) -> None:
    workspace = WorkspaceManager(tmp_path)
    registry = ToolRegistry()
    register_default_tools(registry, workspace, mode="auto")

    tools = registry.list_tools()
    assert any(item["name"] == "read_file" for item in tools)
    assert any(item["name"] == "execute_command" for item in tools)

    capabilities = CapabilityManager(registry)
    cap_map = capabilities.as_dict()
    assert any(item["available"] for item in cap_map["file_operations"])
    assert any(item["available"] for item in cap_map["execution"])


def test_doctor_report(tmp_path: Path) -> None:
    workspace = WorkspaceManager(tmp_path)
    registry = ToolRegistry()
    register_default_tools(registry, workspace, mode="auto")
    capabilities = CapabilityManager(registry)
    doctor = AgentDoctor(registry, capabilities, tmp_path)

    report = doctor.report()
    assert report["tool_count"] > 0
    assert "health" in report
    assert "recommended_improvements" in report
