from pathlib import Path

import pytest

from coding_agent.execution.command_runner import SandboxPolicy, run_command
from coding_agent.governance.approval import ApprovalError, ApprovalPolicy
from coding_agent.governance.safety import SafetyError, validate_command


def test_approval_blocks_unapproved_high_impact_action(tmp_path: Path) -> None:
    policy = ApprovalPolicy(require_approval=True, approved_actions=set())
    sandbox = SandboxPolicy(approval_policy=policy)

    with pytest.raises(ApprovalError):
        run_command("pip install pytest", repo_path=tmp_path, policy=sandbox)


def test_scoped_write_paths_reject_out_of_scope_write(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(SafetyError):
        validate_command(
            "echo hi > ../outside.txt",
            require_allowlist=True,
            repo_path=allowed,
            scoped_write_paths=[allowed],
        )
