from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class ApprovalError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovalPolicy:
    require_approval: bool = False
    approved_actions: set[str] = field(default_factory=set)
    audit_path: Path | None = None


HIGH_IMPACT_ACTIONS = {
    "install_dependencies",
    "filesystem_delete",
    "git_history_rewrite",
    "network_publish",
    "container_run",
}


def classify_action(command: str) -> str:
    normalized = command.lower()

    if "docker " in normalized or "podman " in normalized:
        return "container_run"
    if any(token in normalized for token in ["pip install", "npm install", "mvn dependency", "poetry add"]):
        return "install_dependencies"
    if any(token in normalized for token in ["rm ", "del ", "rmdir ", "git clean -fd"]):
        return "filesystem_delete"
    if "git reset --hard" in normalized or "git rebase" in normalized:
        return "git_history_rewrite"
    if any(token in normalized for token in ["publish", "deploy", "push "]):
        return "network_publish"
    return "generic_command"


def enforce_approval(command: str, policy: ApprovalPolicy) -> dict[str, str | bool]:
    action = classify_action(command)
    is_high_impact = action in HIGH_IMPACT_ACTIONS
    approved = True

    if is_high_impact and policy.require_approval and action not in policy.approved_actions:
        approved = False
        _emit_audit(policy, command=command, action=action, approved=approved)
        raise ApprovalError(f"Approval required for high-impact action: {action}")

    _emit_audit(policy, command=command, action=action, approved=approved)
    return {"action": action, "high_impact": is_high_impact, "approved": approved}


def _emit_audit(policy: ApprovalPolicy, command: str, action: str, approved: bool) -> None:
    if policy.audit_path is None:
        return

    policy.audit_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "approval_check",
        "action": action,
        "approved": approved,
        "command": command,
    }
    with policy.audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
