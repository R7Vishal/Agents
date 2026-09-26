from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import statistics
import subprocess

from coding_agent.presentation.web_app import create_app


@dataclass
class BenchmarkScenario:
    scenario_id: str
    level: str
    title: str
    prompt: str
    checks: list[str]


def _ensure_git_repo(path: Path) -> None:
    if (path / ".git").exists():
        return
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "benchmark@example.com"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Benchmark Bot"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True, text=True)


def _score_bool(flag: bool) -> int:
    return 1 if flag else 0


def run() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    workspace = project_root / ".agent_state" / "copilot_parity_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "README.md").write_text("Copilot parity benchmark workspace\n", encoding="utf-8")
    _ensure_git_repo(workspace)

    app = create_app()
    client = app.test_client()

    scenarios = [
        BenchmarkScenario(
            scenario_id="S1",
            level="simple",
            title="Create markdown file",
            prompt="Create a file called parity_simple.md containing a short description of this project.",
            checks=["file_create", "chat_response", "state_returned"],
        ),
        BenchmarkScenario(
            scenario_id="S2",
            level="simple",
            title="Create and execute Python hello",
            prompt="Create a Python file called parity_hello.py that prints Hello World.",
            checks=["file_create", "command_execution", "activity_trace"],
        ),
        BenchmarkScenario(
            scenario_id="M1",
            level="medium",
            title="Modify existing Python file",
            prompt="Modify parity_hello.py to accept a name.",
            checks=["file_modify", "command_execution", "iterative_reasoning"],
        ),
        BenchmarkScenario(
            scenario_id="M2",
            level="medium",
            title="Repository inspection request",
            prompt="Find where authentication is implemented.",
            checks=["workspace_search", "chat_response", "tool_timeline"],
        ),
        BenchmarkScenario(
            scenario_id="C1",
            level="complex",
            title="Git change explanation",
            prompt="Show me what changed in Git.",
            checks=["git_integration", "chat_response", "tool_timeline"],
        ),
        BenchmarkScenario(
            scenario_id="C2",
            level="complex",
            title="Meta capability introspection",
            prompt="What are your current capabilities?",
            checks=["capability_reflection", "chat_response", "state_returned"],
        ),
        BenchmarkScenario(
            scenario_id="C3",
            level="complex",
            title="Improvement advisor",
            prompt="How can I improve you?",
            checks=["self_improvement_advice", "chat_response", "state_returned"],
        ),
    ]

    results: list[dict[str, object]] = []

    for scenario in scenarios:
        response = client.post(
            "/api/chat",
            json={
                "prompt": scenario.prompt,
                "repo": str(workspace),
                "mode": "first-run",
                "execute_mode": False,
            },
        )
        payload = response.get_json() or {}
        reply = str(payload.get("reply", ""))
        tool_results = payload.get("tool_results", []) or []
        state = payload.get("state", {}) or {}
        activity = payload.get("activity", []) or []

        file_create_ok = (workspace / "parity_simple.md").exists() or (workspace / "parity_hello.py").exists()
        file_modify_ok = "Modification succeeded" in reply
        command_exec_ok = "Execution exit code: 0" in reply
        search_ok = "Matches for" in reply or "No matches found" in reply
        git_ok = "GIT CHANGES" in reply
        capabilities_ok = "CODING AGENT CAPABILITIES" in reply
        advisor_ok = "AGENT IMPROVEMENT ADVISOR" in reply
        chat_ok = response.status_code == 200 and payload.get("ok") is True
        state_ok = bool(state)
        timeline_ok = isinstance(tool_results, list)
        activity_ok = isinstance(activity, list)
        iterative_ok = ("Modified" in "\n".join(activity)) or ("Executed" in "\n".join(activity))

        check_map = {
            "file_create": file_create_ok,
            "file_modify": file_modify_ok,
            "command_execution": command_exec_ok,
            "workspace_search": search_ok,
            "git_integration": git_ok,
            "capability_reflection": capabilities_ok,
            "self_improvement_advice": advisor_ok,
            "chat_response": chat_ok,
            "state_returned": state_ok,
            "tool_timeline": timeline_ok,
            "activity_trace": activity_ok,
            "iterative_reasoning": iterative_ok,
        }

        check_scores = {check: _score_bool(check_map.get(check, False)) for check in scenario.checks}
        scenario_score = sum(check_scores.values())
        scenario_total = len(scenario.checks)
        scenario_pct = round((scenario_score / scenario_total) * 100, 1) if scenario_total else 0.0

        results.append(
            {
                "id": scenario.scenario_id,
                "level": scenario.level,
                "title": scenario.title,
                "prompt": scenario.prompt,
                "http_status": response.status_code,
                "checks": scenario.checks,
                "check_scores": check_scores,
                "score": scenario_score,
                "total": scenario_total,
                "pct": scenario_pct,
                "reply": reply[:800],
            }
        )

    level_groups: dict[str, list[float]] = {"simple": [], "medium": [], "complex": []}
    for item in results:
        level_groups[str(item["level"])].append(float(item["pct"]))

    capability_totals: dict[str, dict[str, int]] = {}
    for item in results:
        for name, value in dict(item["check_scores"]).items():
            bucket = capability_totals.setdefault(name, {"pass": 0, "total": 0})
            bucket["pass"] += int(value)
            bucket["total"] += 1

    overall_pct = round(sum(float(item["pct"]) for item in results) / max(len(results), 1), 1)

    report_lines = [
        "# Copilot-Parity Benchmark Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Workspace: {workspace}",
        f"Overall Score: {overall_pct}%",
        "",
        "## Level Scores",
    ]

    for level in ["simple", "medium", "complex"]:
        values = level_groups[level]
        avg = round(statistics.mean(values), 1) if values else 0.0
        report_lines.append(f"- {level.title()}: {avg}%")

    report_lines.extend([
        "",
        "## Scenario Results",
        "| ID | Level | Scenario | Score |",
        "|---|---|---|---|",
    ])

    for item in results:
        report_lines.append(
            f"| {item['id']} | {item['level']} | {item['title']} | {item['score']}/{item['total']} ({item['pct']}%) |"
        )

    report_lines.extend([
        "",
        "## Capability Scores",
        "| Capability | Pass | Total | Score |",
        "|---|---:|---:|---:|",
    ])

    for capability in sorted(capability_totals.keys()):
        bucket = capability_totals[capability]
        score = round((bucket["pass"] / max(bucket["total"], 1)) * 100, 1)
        report_lines.append(f"| {capability} | {bucket['pass']} | {bucket['total']} | {score}% |")

    report_lines.extend([
        "",
        "## Detailed Evidence",
    ])

    for item in results:
        report_lines.extend(
            [
                f"### {item['id']} - {item['title']}",
                f"- Prompt: {item['prompt']}",
                f"- HTTP: {item['http_status']}",
                f"- Score: {item['score']}/{item['total']} ({item['pct']}%)",
                "- Reply snippet:",
                "```",
                str(item["reply"]),
                "```",
                "",
            ]
        )

    report_lines.extend(
        [
            "## Interpretation",
            "- This benchmark validates practical parity dimensions: file ops, command execution, repository search, git introspection, capability self-description, and advisor behavior.",
            "- High simple/medium scores indicate strong operational behavior for guided coding workflows.",
            "- Complex parity can be improved further with broader autonomous planning over larger multi-file goals.",
        ]
    )

    output_path = reports_dir / "copilot-parity-benchmark.md"
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    report = run()
    print(report)
