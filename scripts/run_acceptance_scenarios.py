from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from coding_agent.presentation.web_app import create_app


def run() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    workspace = project_root / ".agent_state" / "acceptance_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("Acceptance workspace\n", encoding="utf-8")

    if not (workspace / ".git").exists():
        subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "acceptance@example.com"], cwd=workspace, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Acceptance Bot"], cwd=workspace, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "README.md"], cwd=workspace, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=workspace, check=True, capture_output=True, text=True)

    app = create_app()
    client = app.test_client()

    scenarios = [
        {
            "id": 1,
            "prompt": "Create a file called hello.md containing a short description of this project.",
            "check": lambda data: (workspace / "hello.md").exists() and data.get("ok") is True,
        },
        {
            "id": 2,
            "prompt": "Create a Python file called hello.py that prints Hello World.",
            "check": lambda data: (workspace / "hello.py").exists() and "Hello World" in json.dumps(data),
        },
        {
            "id": 3,
            "prompt": "Modify hello.py to accept a name.",
            "check": lambda data: "Execution exit code" in str(data.get("reply", "")) and "Hello Copilot" in json.dumps(data),
        },
        {
            "id": 4,
            "prompt": "What files are in this project?",
            "check": lambda data: "PROJECT STRUCTURE" in str(data.get("reply", "")),
        },
        {
            "id": 5,
            "prompt": "What can you do?",
            "check": lambda data: "CODING AGENT CAPABILITIES" in str(data.get("reply", "")),
        },
        {
            "id": 6,
            "prompt": "How can I improve you?",
            "check": lambda data: "AGENT IMPROVEMENT ADVISOR" in str(data.get("reply", "")),
        },
        {
            "id": 7,
            "prompt": "Show me what changed in Git.",
            "check": lambda data: "GIT CHANGES" in str(data.get("reply", "")),
        },
        {
            "id": 8,
            "prompt": "Create a small application, run its tests, and fix any failures.",
            "check": lambda data: data.get("ok") is True,
        },
    ]

    results: list[dict[str, object]] = []
    for scenario in scenarios:
        response = client.post(
            "/api/chat",
            json={
                "prompt": scenario["prompt"],
                "repo": str(workspace),
                "mode": "first-run",
                "execute_mode": False,
            },
        )
        data = response.get_json() or {}
        ok = response.status_code == 200 and scenario["check"](data)
        results.append(
            {
                "id": scenario["id"],
                "prompt": scenario["prompt"],
                "http_status": response.status_code,
                "pass": ok,
                "reply": str(data.get("reply", ""))[:1200],
                "activity": data.get("activity", []),
                "tool_results": data.get("tool_results", []),
                "state": data.get("state", {}),
            }
        )

    passed = sum(1 for item in results if item["pass"])
    total = len(results)

    report_path = reports_dir / "acceptance-scenarios-report.md"
    lines = [
        "# Conversational Acceptance Scenarios Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Workspace: {workspace}",
        f"Result: {passed}/{total} passed",
        "",
    ]

    for item in results:
        status = "PASS" if item["pass"] else "FAIL"
        lines.append(f"## Scenario {item['id']} - {status}")
        lines.append(f"Prompt: {item['prompt']}")
        lines.append(f"HTTP: {item['http_status']}")
        lines.append("")
        lines.append("Reply:")
        lines.append("```")
        lines.append(str(item["reply"]))
        lines.append("```")
        lines.append("")
        lines.append("Activity:")
        lines.append("```")
        lines.append("\n".join(str(x) for x in item.get("activity", [])))
        lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    output = run()
    print(output)
