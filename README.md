# Coding Agent

Production-focused autonomous coding agent scaffold based on your specification.

## Current milestone

Implemented **FIRST RUN** workflow:
- Repository discovery and architecture mapping
- Baseline verification command discovery + optional execution
- Working/incomplete capability assessment
- Risk and technical debt extraction
- Recommended smallest next milestone
- No target repository file modification during discovery mode

Implemented **controlled execution milestone**:
- Task graph loading with dependency validation
- Controlled task execution (`command` then `validate_command`)
- Failure classification and bounded repair loop
- Repair budget per task with BLOCKED/FAILED completion gate

## Quick start

```powershell
cd coding-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
coding-agent first-run --repo ..\eai-7536-countrycxs
```

## Chat UI (prompt window)

Start local UI:

```powershell
coding-agent-ui
```

Open:

```text
http://127.0.0.1:5050
```

From the chat page you can:
- paste prompt text in the textarea
- set repo path and output report path
- run conversational chat with session memory (Copilot-style prompt/response flow)
- trigger execution explicitly with `/run first-run` or `/run run-plan`
- optionally enable **Execute selected mode on send** for immediate execution
- run `first-run` and `run-plan` using mode settings, plan path, and resume options
- rotate checkpoint key from UI
- view async progress status + timeline details while job is running
- provide file parameters using prompt file upload, context file uploads, and repo-relative context file paths
- view project reference path where this app is created
- download repo source code as `.zip` from UI

## LLM layer policy (current)

- No external LLM integration is enabled by default.
- No Ollama/OpenAI/Azure dependencies are installed for runtime inference.
- The project includes an abstraction-only reasoning layer for future plug-in.

Implemented abstraction modules:
- `src/coding_agent/reasoning/types.py`
- `src/coding_agent/reasoning/router.py`
- `src/coding_agent/reasoning/provider.py`

Current default behavior:
- `ModelRouter` applies hardware-aware routing heuristics:
	- easy tasks -> `Qwen2.5-Coder-3B-Instruct Q4` profile
	- medium/hard local tasks -> `Qwen2.5-Coder-7B-Instruct Q4` profile
	- cloud fallback remains disabled by policy
- `LLMGateway` uses `NullLLMProvider` until a real provider is registered.

You can inspect routing decisions via API (no model call):

```text
POST /api/reasoning/route
```

## VS Code configurable agent

This project now supports a workspace-configurable execution model for VS Code.

### Workspace config

Edit:

```text
.vscode/coding-agent.json
```

Key fields:
- `mode`: `first-run` | `run-plan` | `rotate-key`
- `repo`: target repository path
- `output`: report output path
- `plan_file`: required for `run-plan`
- `max_repair_attempts_per_task`, `resume_*` controls for run-plan

### Run from terminal using config

```powershell
coding-agent run-config --config .vscode/coding-agent.json
```

Optional mode override:

```powershell
coding-agent run-config --config .vscode/coding-agent.json --mode run-plan
```

### Run from VS Code

- Open **Command Palette** → **Tasks: Run Task**
	- `Coding Agent: Run Config`
	- `Coding Agent: Run Config (first-run)`
	- `Coding Agent: Run Config (run-plan)`
	- `Coding Agent: Rotate Key`
	- `Coding Agent: UI`

Debug launch profiles are also provided in `.vscode/launch.json`.

## Export and install on a different machine

Yes, this agent can be exported and installed on another machine running VS Code.

### 1) Export on source machine

From project root:

```powershell
.\scripts\export-agent.ps1 -OutputZip coding-agent-portable.zip
```

This creates a portable zip containing source, tests, examples, `.vscode` tasks/launch config, and docs.

### 2) Copy and extract on target machine

- Copy `coding-agent-portable.zip` to target machine
- Extract into a folder (for example `C:\dev\coding-agent`)
- Open that folder in VS Code

### 3) Install dependencies on target machine

From the extracted project root:

```powershell
.\scripts\install-agent.ps1 -ProjectPath . -RunTests
```

If editable install fails with a file-lock error, close running `coding-agent-ui` / Python terminals and re-run the installer.

### 4) Run in VS Code

- Use **Tasks: Run Task**:
	- `Coding Agent: UI`
	- `Coding Agent: Run Config`
- Or run from terminal:

```powershell
.venv\Scripts\coding-agent run-config --config .vscode/coding-agent.json
```

### Prerequisites on target machine

- Python `3.10+`
- VS Code
- Recommended extension: `ms-python.python`

Run with baseline command execution:

```powershell
coding-agent first-run --repo ..\eai-7536-countrycxs --run-baseline
```

Save report:

```powershell
coding-agent first-run --repo ..\eai-7536-countrycxs --output reports\assessment.md
```

Run a controlled plan with repair budget:

```powershell
coding-agent run-plan --repo . --plan-file examples\simple-plan.json --max-repair-attempts-per-task 2 --output reports\plan-run.md
```

Resume an interrupted or blocked plan:

```powershell
coding-agent run-plan --repo . --plan-file examples\simple-plan.json --resume-latest --output reports\plan-resume.md
```

Preview resume queue without executing commands:

```powershell
coding-agent run-plan --repo . --plan-file examples\simple-plan.json --resume-latest --resume-dry-run --resume-max-risk 3 --output reports\resume-preview.md
```

Resume preview includes retry risk scoring (`LOW|MEDIUM|HIGH`) and reasons for each retried task.
Resume preview also includes per-task repair recommendations.

Or resume by explicit run ID:

```powershell
coding-agent run-plan --repo . --plan-file examples\simple-plan.json --resume-run-id <run-id>
```

Structured JSONL logs are written under `.agent_logs/<run-id>.jsonl` and include per-task duration metrics (`duration_ms`) on completion/failure events.

Checkpoint data now uses HMAC-signed envelopes (`HMAC-SHA256`). If checkpoint state is tampered, resume is blocked with an integrity-check forensic report.

When integrity mismatch is detected, the command returns a forensic report with expected/actual hash details and checkpoint task IDs.

Rotate checkpoint signing key (keeps backward verification for previously signed checkpoints):

```powershell
coding-agent rotate-key --output reports\key-rotation.md
```

Checkpoint envelope versioning:
- `v2`: HMAC signature + `key_id` (current default)
- `v1`: HMAC signature without `key_id` (supported for backward compatibility)
- legacy: plain `hash` envelope (still verifiable for backward compatibility)

Risk-threshold policy:

```powershell
coding-agent run-plan --repo . --plan-file examples\resume-blocked-plan.json --resume-latest --resume-max-risk 3 --output reports\resume-policy-block.md
```

If retry tasks exceed the threshold, execution is blocked and a policy report is returned.

## Safety defaults

- Discovery mode performs read-only repository inspection.
- Destructive shell operations are blocked.
- Target writes are blocked in FIRST RUN mode.

## Project structure

- `src/coding_agent/main.py` CLI entrypoint
- `src/coding_agent/orchestration/agent.py` orchestration loop (moved)
- `src/coding_agent/presentation/web_app.py` Flask UI/API (moved)
- `src/coding_agent/presentation/chat_service.py` conversational layer (moved)
- `src/coding_agent/reasoning/` model routing + provider abstraction (no runtime integration)
- `src/coding_agent/execution/` task graph, command runner, repair, verifier (moved)
- `src/coding_agent/governance/` safety, lifecycle, integrity (moved)
- `src/coding_agent/composition.py` layer composition root
- `src/coding_agent/layers/` architecture contracts + integration mapping
- `src/coding_agent/repo_intel.py` repository intelligence
- `src/coding_agent/planner.py` next-milestone selection
- `src/coding_agent/state_store.py` lifecycle persistence
- `src/coding_agent/reporting.py` final assessment rendering
- `tests/` unit tests

Compatibility shims retained for import stability:
- `src/coding_agent/web_app.py`
- `src/coding_agent/agent.py`
- `src/coding_agent/executor.py`
- `src/coding_agent/task_graph.py`
- `src/coding_agent/command_runner.py`
- `src/coding_agent/repair.py`
- `src/coding_agent/verifier.py`
- `src/coding_agent/safety.py`
- `src/coding_agent/lifecycle.py`
- `src/coding_agent/integrity.py`

## Pre-LLM development roadmap (recommended)

Before integrating any real LLM runtime, complete these steps:

1. **Context quality pipeline**
	- Add symbol index + semantic retrieval adapter behind `CodeSearchPort`
	- Add context packing policy with token budget telemetry
2. **Structured editing engine**
	- Introduce safe edit operations (method replace/insert/import add)
	- Add file-level rollback checkpoints for failed edits
3. **Sandbox hardening**
	- Move command execution into containerized runner profile
	- Enforce command allowlist policy and path-scoped write controls
4. **Validation depth**
	- Add staged validation (`build -> unit -> integration -> static checks`)
	- Add deterministic retry policy by failure class
5. **Governance and audit**
	- Add action approval gates for high-impact operations
	- Expand JSONL event schema to include policy decisions and costs
6. **Persistence and reliability**
	- Persist chat/job state for restart-safe operation
	- Add run replay artifacts for post-incident debugging

Architecture references:
- `LAYERED_AGENT_ARCHITECTURE.md` (12-layer integration model mapped to current code)
- `TECHNICAL_IMPLEMENTATION_DOCUMENT.md` (full implementation detail)
- `LOCAL_MODEL_ROUTING_STRATEGY.md` (hardware-aware model routing abstraction)
