# Technical Details - Coding Agent

## 1) Core technologies

- Language: Python 3.10+
- Web framework: Flask 3.x
- Testing framework: pytest 8.x+
- Packaging: pyproject.toml (editable install supported)
- Runtime style: CLI + Web UI
- UI delivery: Server-rendered HTML + JavaScript from Flask templates
- Environment automation: PowerShell scripts

## 2) Main project components

- Agent orchestration and workflow execution
- Reasoning/router abstraction with provider contract harness
- Retrieval adapter and structured editing layer with rollback
- Safety/approval governance and staged validation pipeline
- Web UI for planning, approval, execution, and activity trace
- Workspace manager + centralized tool registry + dynamic capability manager
- Persistent semantic index and approval-token safety workflow
- Acceptance and Copilot-parity benchmark automation scripts

## 3) Required tools to run on Windows

- Windows PowerShell 5.1 or PowerShell 7+
- Python 3.10 or newer available on PATH
- pip (bundled with Python)
- Git (recommended for diff stats, git panel, and version workflows)

## 4) Optional tools (based on workflow)

- Docker Desktop (only if using container sandbox profile)
- VS Code (recommended for tasks, launch config, and extension support)

## 5) Python dependencies

From requirements.txt:

- flask>=3.0.0
- pytest>=8.3.0

Project is also installed in editable mode:

- pip install -e .

## 6) How to install prerequisites and run

Use the new script:

- scripts/setup-and-run-agent.ps1

Supported modes:

- ui (default): installs dependencies and starts Coding Agent UI
- run-config: installs dependencies and runs configured workflow

Examples:

- powershell -ExecutionPolicy Bypass -File .\scripts\setup-and-run-agent.ps1 -Mode ui
- powershell -ExecutionPolicy Bypass -File .\scripts\setup-and-run-agent.ps1 -Mode run-config -RunTests

## 7) Existing helper scripts

- scripts/install-agent.ps1
  - Creates venv, installs dependencies, editable install, optional tests
- scripts/export-agent.ps1
  - Exports full project code as zip (with safe exclusions)
- scripts/run-provider-contract-tests.ps1
  - Runs provider contract/fallback harness tests
- scripts/run_acceptance_scenarios.py
  - Executes conversational acceptance scenarios (1-8) and writes report
- scripts/run_copilot_parity_benchmark.py
  - Executes graded simple/medium/complex parity benchmark and writes scored report

## 8) Export for another machine

Run:

- powershell -ExecutionPolicy Bypass -File .\scripts\export-agent.ps1 -OutputZip coding-agent-portable.zip

This creates:

- coding-agent-portable.zip in project root

## 9) New UI and API operational features

- Guide page: `GET /guide`
- One-click acceptance run: `POST /api/acceptance/run`
- Acceptance report view: `GET /api/acceptance/report`
- Semantic index rebuild: `POST /api/index/rebuild`
- Reasoning telemetry: `GET /api/reasoning/telemetry`
- Approval workflow:
  - `POST /api/approvals/request`
  - `POST /api/approvals/approve`
  - `GET /api/approvals`

## 10) Verification checklist

- python --version returns 3.10+
- setup-and-run script completes without errors
- UI opens at http://127.0.0.1:5050 (ui mode)
- python -m pytest -q passes when test dependencies are installed
- zip export file exists in project root
- acceptance report generated at `reports/acceptance-scenarios-report.md`
- parity benchmark report generated at `reports/copilot-parity-benchmark.md`
