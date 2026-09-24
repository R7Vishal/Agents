# Coding Agent - Technical Implementation Document

## 1) Document Control

- **Project**: `coding-agent`
- **Version**: `0.1.0`
- **Runtime**: Python `>=3.10`
- **Primary Interfaces**: CLI + Flask Web UI
- **Date**: 2026-09-24

---

## 2) Purpose and Scope

This document describes the current implementation of the Coding Agent, including:

- Core architecture and module responsibilities
- CLI and Web API contracts
- Execution state machine and checkpointing
- Integrity and resume controls
- Conversational chat behavior (Copilot-like UI mode)
- Observability, testing, and operational guidance

### 2.1 In-Scope

- First-run repository assessment workflow
- Controlled plan execution with dependency ordering
- Validation/repair budget enforcement
- Resume and risk-threshold policy handling
- Checkpoint integrity with HMAC signing + key rotation
- Web UI async execution orchestration
- Session-based conversational endpoint

### 2.2 Out-of-Scope

- External LLM provider integration (OpenAI/Azure/OpenRouter)
- Multi-user authN/authZ for API access
- Distributed task execution across workers
- Persistent DB-backed chat history (chat session history is in-memory)

---

## 3) High-Level Architecture

The system follows a modular local-orchestration architecture:

1. **Entry layer**
   - CLI (`coding-agent`) for scripted/local automation
   - Flask UI/API (`coding-agent-ui`) for interactive operation
2. **Orchestration layer**
   - `CodingAgent` coordinates discovery, plan execution, state transitions, reporting
3. **Execution layer**
   - Task graph loader/validator/scheduler + command runner + repair classifier
4. **State and integrity layer**
   - Run records in `.agent_state/*.json`
   - Checkpoints signed with HMAC envelopes and keyring support
5. **Observability layer**
   - JSONL event stream per run in `.agent_logs/<run-id>.jsonl`
6. **Presentation layer**
   - Markdown report renderers and web chat UI template

---

## 4) Source Layout and Responsibilities

### 4.1 Entrypoints

- `src/coding_agent/main.py`
  - Defines CLI parser and subcommands (`first-run`, `run-plan`, `rotate-key`)
  - Resolves requirement text from inline arg or `--requirement-file`
  - Emits markdown report to stdout or file

- `src/coding_agent/presentation/web_app.py`
  - Flask app factory (`create_app`)
  - Serves chat UI (`/`)
  - Exposes operational APIs (`/api/*`)
  - Manages in-process async job queue for long-running runs

### 4.2 Core orchestration

- `src/coding_agent/orchestration/agent.py`
  - Implements `CodingAgent` class
  - Coordinates repository analysis, baseline checks, planning recommendation
  - Executes controlled task graph with checkpointing and recovery
  - Enforces resume risk policy and integrity verification
  - Rotates signing keys and persists run outcomes

### 4.3 Execution components

- `src/coding_agent/execution/task_graph.py`
  - Loads plan JSON into `TaskGraph`
  - Validates graph integrity (duplicate IDs, unknown deps)
  - Computes ready tasks and terminal state
  - Snapshots/applies checkpoints

- `src/coding_agent/execution/executor.py`
  - Runs ready tasks in dependency order
  - Executes `command` then optional `validate_command`
  - Applies bounded repair loop via `repair_commands`
  - Emits structured per-task outcomes with duration metrics

- `src/coding_agent/execution/command_runner.py`
  - Wraps subprocess execution (`shell=True`) with timeout
  - Applies safety policy before execution
  - Normalizes `python ...` commands to current interpreter

- `src/coding_agent/execution/repair.py`
  - Classifies failures into normalized `FailureType`

### 4.4 Discovery and recommendation

- `src/coding_agent/repo_intel.py`
  - File-level repository discovery and classification
  - Detects manifests, entry points, tests, prompts, planner/lifecycle/safety files
  - Extracts TODO/FIXME markers

- `src/coding_agent/planner.py`
  - Rule-based “smallest next milestone” recommendation

- `src/coding_agent/execution/verifier.py`
  - Candidate baseline checks (pytest, compileall, npm test, maven test)
  - Optional execution with command safety validation

### 4.5 Lifecycle, state, and integrity

- `src/coding_agent/governance/lifecycle.py`
  - Allowed state transition matrix and guard function

- `src/coding_agent/state_store.py`
  - Persist/load run records as JSON
  - Enforce guarded transitions
  - Retrieve latest run

- `src/coding_agent/governance/integrity.py`
  - HMAC keyring load/create
  - Active key resolution
  - Signature envelope wrapping and verification
  - Backward compatibility for legacy hash envelopes
  - Forensic detail generation for integrity failures

### 4.6 Reporting and observability

- `src/coding_agent/reporting.py`
  - Builds first-run assessment model
  - Renders markdown for first-run, execution summaries, resume preview, integrity forensics, policy blocks

- `src/coding_agent/observability.py`
  - JSONL logger (`timestamp`, `event`, payload)

### 4.7 Chat service

- `src/coding_agent/presentation/chat_service.py`
  - In-memory session store with bounded history
  - Intent-aware reply strategies (help, context, repository summary, generic assistant response)
  - Integrates with web API action inference to support conversational + executable chat

### 4.8 Reasoning abstraction layer

- `src/coding_agent/reasoning/types.py`
  - Core routing and hardware profile dataclasses
- `src/coding_agent/reasoning/router.py`
  - Heuristic task complexity classifier + model route selection
- `src/coding_agent/reasoning/provider.py`
  - `LLMProvider` protocol, `LLMGateway`, and `NullLLMProvider`

Note: this project currently keeps reasoning as abstraction only; no runtime LLM provider is wired.

### 4.9 UI template

- `src/coding_agent/templates/index.html`
  - Copilot-style split layout (settings + chat thread + composer)
  - Async job polling and progress timeline
  - File parameter support (prompt file + context files/paths)
  - Chat-first send behavior with optional execute-on-send

---

## 5) Data Model

Primary dataclasses and enums are defined in `src/coding_agent/models.py`.

### 5.1 Lifecycle and status enums

- `LifecycleState`: `IDLE`, `ANALYZING`, `PLANNING`, `READY`, `EXECUTING`, `VALIDATING`, `REPAIRING`, `BLOCKED`, `COMPLETED`, `FAILED`
- `TaskStatus`: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `BLOCKED`
- `FailureType`: syntax/import/dependency/type/test/build/runtime/config/environment/timeout/unknown classes

### 5.2 Core records

- `AgentRunRecord`
  - `run_id`, `requirement`, `state`, `repo_path`, `notes`, `updated_at`
- `TaskNode`
  - Task contract including dependencies, repair commands, attempt counters, status/failure metadata
- `TaskExecutionResult`
  - Terminal result with attempts, repairs, failure class, message, `duration_ms`

---

## 6) Execution Lifecycle

### 6.1 First-run assessment (`first-run`)

1. Create run record in `ANALYZING`
2. Discover repository facts
3. Transition to `VALIDATING`
4. Run/discover baseline checks
5. Transition to `PLANNING`
6. Recommend next milestone
7. Build assessment model
8. Transition to `COMPLETED`
9. Persist notes + render markdown report

### 6.2 Controlled plan execution (`run-plan`)

1. Validate resume flags and policy inputs
2. Resolve run record (new or resume)
3. Load + validate task graph from JSON
4. Verify checkpoint envelope integrity if present
5. Apply checkpoint snapshot to graph
6. Build retry risk queue for non-completed tasks
7. Optionally return dry-run resume preview report
8. Optionally block resume by risk policy
9. Transition to `EXECUTING`
10. Execute graph with repair budgets and task events
11. Persist checkpoint snapshot on each emitted task event
12. Finalize run state (`COMPLETED` or `BLOCKED`)
13. Render execution report

---

## 7) Task Graph Contract

Expected plan JSON shape:

```json
{
  "tasks": [
    {
      "task_id": "T1",
      "description": "...",
      "rationale": "...",
      "command": "python -c \"print('ok')\"",
      "validate_command": "",
      "dependencies": [],
      "expected_result": "",
      "validation_method": "",
      "repair_commands": []
    }
  ]
}
```

Validation rules:

- Task IDs must be unique
- Every dependency must point to an existing task ID

Scheduling behavior:

- `PENDING` tasks with all dependencies `COMPLETED` become ready
- Any task depending on `FAILED/BLOCKED` dependency becomes `BLOCKED`
- Loop exits when all tasks terminal (`COMPLETED`, `FAILED`, `BLOCKED`)

---

## 8) Repair and Failure Handling

### 8.1 Failure classification

`classify_failure(output, timed_out, command)` infers:

- Timeout
- Syntax/import/dependency/type/test/build errors
- Configuration/environment/runtime errors
- Unknown fallback

### 8.2 Repair loop

Per task:

- If command/validate fails, classify failure
- Try up to `max_repair_attempts_per_task`
- Execute `repair_commands` in-order (reuses last command if retries exceed list length)
- Retry original task command after successful repair command
- If retries exhausted, task terminates as `FAILED`

---

## 9) State Persistence and Resume

### 9.1 State files

- Path: `.agent_state/<run-id>.json`
- Store `AgentRunRecord` with lifecycle, metadata, and latest checkpoint payload

### 9.2 Resume modes

- `--resume-run-id <id>`: resume specific run
- `--resume-latest`: resume most recent run from state dir
- Guards:
  - Repo path must match
  - Plan path must match
  - Run must not already be `COMPLETED`

### 9.3 Resume dry run

`--resume-dry-run` outputs retry queue, risk scores, and recommendations without executing commands.

---

## 10) Checkpoint Integrity and Key Management

### 10.1 Envelope formats

- **v2** (default): `{data, algorithm, signature_version, signature, key_id}`
- **v1**: same but no `key_id` (resolved by scanning keyring)
- **legacy**: hash-based envelope (`hash`) still verifiable for backward compatibility

### 10.2 Keyring

- File: `.agent_state/.checkpoint_hmac_keyring.json`
- Fields: `version`, `active_key_id`, `keys`
- Rotations append new key (`kN`) and set active key

### 10.3 Verification and forensics

- If signature/hash mismatch detected:
  - run transitions to `BLOCKED`
  - forensic report generated with expected/actual hash/signature and checkpoint task inventory

---

## 11) Conversational Chat Implementation

### 11.1 Session model

- Sessions are in-memory dictionary keyed by `session_id`
- Each session stores chronological message list with role + timestamp
- History length bounded by `max_history` (default 30 messages)

### 11.2 Response strategy

The chat service uses deterministic intent routing:

- Greeting intent
- Help/capability intent
- Context/history recall intent
- Repo/architecture summary intent (uses discovery + planner)
- Generic fallback intent

### 11.3 Action inference

`web_app._infer_action(...)` detects execution intent from:

- Explicit toggle (`execute_mode`)
- Slash command (`/run first-run`, `/run run-plan`)
- Natural phrases (“execute plan”, “first run”)

If action is inferred:

- `/api/chat` can dispatch async execution job and return `job_id`
- Otherwise returns pure conversational reply

## 11.4 Reasoning abstraction (no provider integration)

- `ModelRouter` applies hardware-aware route recommendation (`3B` vs `7B` profile, optional cloud fallback policy)
- `LLMGateway` resolves provider by model key
- `NullLLMProvider` is default and guarantees deterministic no-model behavior

This keeps architecture ready for future providers without adding runtime inference dependencies today.

---

## 12) Web API Specification

Base server: `http://127.0.0.1:5050`

### 12.1 `GET /`

- Returns chat UI HTML template

### 12.2 `GET /api/project-info`

- Response:
  - `ok: bool`
  - `project_root: str`

### 12.3 `GET /api/download-project?repo=<path>`

- Returns source zip stream for repo path
- Excludes: `.venv`, `__pycache__`, `.pytest_cache`, `.git`, `node_modules`, `*.pyc`, `*.pyo`

### 12.4 `POST /api/chat`

- Request (core):
  - `prompt`, `session_id?`, `repo`, `mode`, `execute_mode?`, `plan_file?`, execution parameters, attachments/context paths
- Response:
  - Always returns conversational `reply`
  - Returns `action` if execution intent inferred
  - Returns `job_id` when async execution dispatched

### 12.5 `POST /api/first-run`

- Executes first-run workflow
- Supports `async_mode`

### 12.6 `POST /api/run-plan`

- Executes controlled plan workflow
- Supports `async_mode`

### 12.7 `GET /api/job/<job_id>`

- Polls async job status
- Returns `queued/running/completed/failed`, progress, details timeline, and result/error

### 12.8 `POST /api/rotate-key`

- Rotates checkpoint HMAC key
- Returns `new_key_id`, `total_keys`

### 12.9 `POST /api/reasoning/route`

- Returns heuristic routing decision for a prompt without invoking any model
- Request:
  - `prompt: str` (required)
  - `context_tokens: int` (optional)
- Response:
  - `ok: bool`
  - `decision: { complexity, selected_model_key, selected_model_label, context_tokens, local_only, reason, fallback_model_key }`

---

## 13) CLI Specification

Command group is exposed by project script `coding-agent`.

### 13.1 `coding-agent first-run`

- Required: `--repo`
- Optional:
  - `--requirement`
  - `--requirement-file`
  - `--run-baseline`
  - `--output`

### 13.2 `coding-agent run-plan`

- Required: `--repo`, `--plan-file`
- Optional:
  - `--requirement`, `--requirement-file`
  - `--max-repair-attempts-per-task`
  - `--resume-run-id`, `--resume-latest`
  - `--resume-dry-run`, `--resume-max-risk`
  - `--output`

### 13.3 `coding-agent rotate-key`

- Optional: `--output`

### 13.4 `coding-agent run-config`

- Purpose: run the agent from a workspace JSON configuration (VS Code-friendly)
- Arguments:
  - `--config` (default: `.vscode/coding-agent.json`)
  - `--mode` optional override (`first-run|run-plan|rotate-key`)

The command loads JSON fields such as `repo`, `requirement`, `output`, `plan_file`, and resume/repair controls, then dispatches to the corresponding workflow.

---

## 14) Safety Model

### 14.1 Command guard

Before command execution, blocked tokens are rejected (case-insensitive), including:

- `rm -rf`, `del /s`, `rmdir /s`
- `git reset --hard`, `git clean -fd`
- `shutdown`, `reboot`

### 14.2 Baseline and task execution

- Same safety validator applies to baseline checks and task commands
- Timeout is enforced by subprocess wrapper (default 600 seconds)

---

## 15) Observability

### 15.1 Run event logs

- Path: `.agent_logs/<run-id>.jsonl`
- Event examples:
  - `run_started`, `state_transition`, `task_event`, `checkpoint_loaded`, `run_completed`, `checkpoint_integrity_failed`, `resume_policy_blocked`

### 15.2 Task metrics

- `duration_ms` captured for completed/failed task results
- Included in execution report and task events

---

## 16) Report Outputs

The system generates markdown reports for:

- First-run assessment
- Plan execution summary and task results
- Resume dry-run preview
- Integrity forensics block
- Resume policy block
- Key rotation status

Reports can be written to user-defined output files via CLI/UI.

---

## 17) UI Behavior (Copilot-style chat window)

- Chat-first interaction mode
- Session-aware responses via `/api/chat`
- Optional immediate execution using toggle or explicit `/run ...` prompt
- Async status bar + detailed progress timeline
- Context augmentation from uploaded files and repo-relative file paths
- Project root display + source zip download + key rotation control

## 17.1 VS Code Workspace Integration

The project includes native workspace integration files:

- `.vscode/coding-agent.json` (agent configuration)
- `.vscode/tasks.json` (run UI, run config, mode-specific tasks, rotate key)
- `.vscode/launch.json` (debug profiles for UI and config-run)
- `.vscode/extensions.json` (recommended Python extensions)

This allows the agent to be run as a configurable VS Code workflow without manual CLI argument repetition.

---

## 18) Build and Runtime Dependencies

From `pyproject.toml` and `requirements.txt`:

- Runtime:
  - `flask>=3.0.0`
- Dev/Test:
  - `pytest>=8.3.0`

Packaging:

- `setuptools` backend
- Console scripts:
  - `coding-agent`
  - `coding-agent-ui`

---

## 19) Test Coverage Overview

Current test modules validate:

- Repository discovery and planner recommendations
- Lifecycle transition guards
- Command safety and runner behavior
- Task graph validation/scheduling
- Executor success/failure/repair behavior
- Resume + integrity workflows and key rotation
- Chat endpoint behavior and execution dispatch

Representative list:

- `tests/test_agent_first_run.py`
- `tests/test_agent_run_plan.py`
- `tests/test_executor.py`
- `tests/test_run_plan_resume.py`
- `tests/test_resume_preview_and_integrity.py`
- `tests/test_key_rotation.py`
- `tests/test_web_chat.py`

---

## 20) Known Constraints and Improvement Opportunities

### 20.1 Current constraints

- Chat memory is process-local and non-persistent
- Async jobs are in-memory; restart drops job history
- `shell=True` command model relies on robust safety token filtering
- No built-in authentication for web endpoints
- No external LLM semantic generation yet

### 20.2 Recommended next enhancements

1. Persist chat sessions and job metadata to durable storage
2. Add API auth (token/session) and CSRF hardening for deployment use
3. Replace heuristic chat replies with pluggable LLM provider abstraction
4. Add richer policy engine (allowlist/denylist per workspace)
5. Add concurrent execution strategy for independent tasks (optional)

### 20.3 Required pre-LLM development steps

Before integrating any real LLM runtime, complete these engineering steps:

1. **Context retrieval readiness**
  - Implement `CodeSearchPort` adapters (file, symbol, semantic retrieval)
  - Add context-packing limits and token budget telemetry
2. **Structured editing safety**
  - Implement `CodeEditingEnginePort` adapters with rollback checkpoints
  - Add invariants for protected files and scoped write policies
3. **Execution isolation hardening**
  - Add containerized sandbox profile for command execution
  - Enforce strict command allowlist and environment profile control
4. **Validation pipeline depth**
  - Standardize staged checks (`build -> unit -> integration -> static`)
  - Add deterministic retry strategy by failure class
5. **Governance and observability gates**
  - Add approval gates for high-impact operations
  - Emit policy/routing/audit events in JSONL schema
6. **Provider plug-in harness**
  - Keep `LLMGateway` default as `NullLLMProvider`
  - Add provider contract tests before wiring any external runtime

---

## 21) Operational Runbook

### 21.1 Local setup

```powershell
cd coding-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

### 21.2 Start UI

```powershell
coding-agent-ui
```

Open `http://127.0.0.1:5050`.

### 21.3 First-run from CLI

```powershell
coding-agent first-run --repo ..\eai-7536-countrycxs --run-baseline --output reports\assessment.md
```

### 21.4 Run plan from CLI

```powershell
coding-agent run-plan --repo . --plan-file examples\simple-plan.json --max-repair-attempts-per-task 2 --output reports\plan-run.md
```

### 21.5 Resume dry-run preview

```powershell
coding-agent run-plan --repo . --plan-file examples\simple-plan.json --resume-latest --resume-dry-run --resume-max-risk 3 --output reports\resume-preview.md
```

### 21.6 Rotate checkpoint key

```powershell
coding-agent rotate-key --output reports\key-rotation.md
```

---

## 22) Appendix A - Primary Files

- `src/coding_agent/main.py`
- `src/coding_agent/orchestration/agent.py`
- `src/coding_agent/presentation/web_app.py`
- `src/coding_agent/presentation/chat_service.py`
- `src/coding_agent/reasoning/router.py`
- `src/coding_agent/reasoning/provider.py`
- `src/coding_agent/reasoning/types.py`
- `src/coding_agent/execution/task_graph.py`
- `src/coding_agent/execution/executor.py`
- `src/coding_agent/execution/command_runner.py`
- `src/coding_agent/governance/integrity.py`
- `src/coding_agent/state_store.py`
- `src/coding_agent/governance/lifecycle.py`
- `src/coding_agent/execution/verifier.py`
- `src/coding_agent/reporting.py`
- `src/coding_agent/observability.py`

---

## 23) Appendix B - Versioning Notes

This document reflects the implementation state that includes:

- Copilot-style chat UI
- `/api/chat` conversational endpoint with action inference
- Resume integrity verification + forensics
- HMAC key rotation and backward envelope compatibility
- Resume max risk policy controls
