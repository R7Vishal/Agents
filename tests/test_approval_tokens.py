from pathlib import Path

from coding_agent.tools import ToolRegistry, register_default_tools
from coding_agent.tools.approval_tokens import ApprovalTokenManager
from coding_agent.workspace_manager import WorkspaceManager


def test_destructive_tools_require_approval_token(tmp_path: Path) -> None:
    workspace = WorkspaceManager(tmp_path)
    approval = ApprovalTokenManager(tmp_path / ".agent_state")
    registry = ToolRegistry()
    register_default_tools(registry, workspace, mode="auto", approval_tokens=approval)

    workspace.create_file("sample.txt", "hello", overwrite=True)

    blocked = registry.execute("delete_file", {"path": "sample.txt", "approved": True})
    assert blocked["success"] is False
    assert blocked.get("approval_required") is True
    req = blocked.get("approval_request")
    assert req and req.get("request_id")

    approved = approval.approve(str(req["request_id"]))
    assert approved["success"] is True
    token = approved["approval_token"]

    deleted = registry.execute(
        "delete_file",
        {"path": "sample.txt", "approved": True, "approval_token": token},
    )
    assert deleted["success"] is True
