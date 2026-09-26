# Layered Architecture - Coding Agent

This document restructures the current codebase into clear architectural layers aligned with your AI Coding Agent model.

## Latest update (2026-09-26)

The architecture has been advanced with production-oriented capabilities:

- Persistent semantic index for repository search (`retrieval/semantic_index.py`)
- Workspace-bounded filesystem manager (`workspace_manager.py`)
- Centralized tool registry + capability manager (`tools/registry.py`, `tools/capabilities.py`)
- Approval-token workflow for destructive actions (`tools/approval_tokens.py`)
- Optional provider-backed LLM integration + telemetry (`reasoning/provider.py`)
- Deeper repair proposals for multi-file patching (`execution/repair_strategies.py`)
- Guide page and one-click benchmark/acceptance UI flows (`/guide`, `/api/acceptance/*`)

## 1) Agent Loop (Core)

The system follows a **Reason -> Act -> Observe -> Repair/Validate** loop:

1. Understand requirement
2. Understand repository
3. Create/update plan
4. Execute tool/action
5. Observe result
6. Diagnose + repair on failure
7. Validate and summarize

Current loop implementation lives primarily in:
- `src/coding_agent/orchestration/agent.py`
- `src/coding_agent/execution/executor.py`
- `src/coding_agent/presentation/web_app.py`

---

## 2) 12-Layer Model and Integration Points

## 2.1 User Interface Layer

**Purpose**: Interaction surface for developers.

**Current implementation**:
- `src/coding_agent/presentation/web_app.py`
- `src/coding_agent/templates/index.html`

**Integration points**:
- `GET /` for chat UI
- `POST /api/chat` conversational+execution trigger
- `POST /api/first-run`, `POST /api/run-plan`
- `GET /api/job/<id>` async status

---

## 2.2 Agent Orchestrator Layer

**Purpose**: Owns end-to-end flow and state transitions.

**Current implementation**:
- `src/coding_agent/orchestration/agent.py::CodingAgent`

**Integration points**:
- `first_run_assessment(...)`
- `run_controlled_plan(...)`
- `rotate_checkpoint_key()`

---

## 2.3 LLM / Reasoning Layer

**Purpose**: Task interpretation, response generation, decision support.

**Current implementation**:
- `src/coding_agent/reasoning/` (abstraction layer)
- `src/coding_agent/presentation/chat_service.py` (rule-based conversational baseline)

**Integration points**:
- `ModelRouter.recommend(...)`
- `LLMGateway.generate(...)`
- `CopilotChatService.reply(...)`

**Current policy decision**:
- Provider abstraction remains default-safe.
- Runtime provider integration is optional and policy-gated via environment variables.
- Telemetry is available at `/api/reasoning/telemetry`.

See: `LOCAL_MODEL_ROUTING_STRATEGY.md`

---

## 2.4 Repository Understanding Layer

**Purpose**: Analyze codebase structure and metadata.

**Current implementation**:
- `src/coding_agent/repo_intel.py`

**Integration points**:
- `discover_repository(repo_path)`

Extracts:
- entry points, manifests, tests, workflows
- planner/lifecycle/safety/persistence hints
- TODO/FIXME markers

---

## 2.5 Code Search / RAG Layer

**Purpose**: Retrieve relevant code context.

**Current implementation status**: **Implemented foundation + persistent semantic index**

**Near-term adapter interface**:
- file search
- symbol search
- semantic search
- dependency and call graph retrieval

Implemented modules:
- `src/coding_agent/retrieval/adapters.py::LocalCodeSearchAdapter`
- `src/coding_agent/retrieval/semantic_index.py::PersistentSemanticIndex`

Defined contracts are in:
- `src/coding_agent/layers/contracts.py::CodeSearchPort`

---

## 2.6 Planning Engine Layer

**Purpose**: Convert analysis to smallest safe next milestone.

**Current implementation**:
- `src/coding_agent/planner.py`

**Integration points**:
- `recommend_next_milestone(facts)`

---

## 2.7 Tool / Function Calling Layer

**Purpose**: Execute tool operations selected by orchestrator/reasoning layer.

**Current implementation**:
- `src/coding_agent/tools/registry.py` (tool contract + execution)
- `src/coding_agent/tools/builders.py` (default toolset)
- `src/coding_agent/workspace_manager.py` (secure workspace file operations)
- dispatch via `src/coding_agent/presentation/chat_service.py` and `web_app.py`

**Integration points**:
- file read/create/write/edit/delete/rename/list/search
- command execution and test execution
- git status/diff/log/branch/add/commit
- endpoint-dispatched first-run/run-plan/rotate-key

---

## 2.8 Code Editing Engine Layer

**Purpose**: Safe structured code edits.

**Current implementation status**: **Implemented foundation**

**Near-term adapter interface**:
- replace text
- insert after anchor
- symbol-aware replace

Implemented modules:
- `src/coding_agent/editing/structured_editor.py`
- `src/coding_agent/presentation/chat_service.py` (repo-scoped create/modify flows)

Defined contracts are in:
- `src/coding_agent/layers/contracts.py::CodeEditingEnginePort`

---

## 2.9 Sandbox / Execution Layer

**Purpose**: Isolated and controlled command execution.

**Current implementation**:
- `src/coding_agent/execution/command_runner.py`
- `src/coding_agent/governance/safety.py`

**Integration points**:
- command allow/block validation
- timeout-aware subprocess execution

---

## 2.10 Test & Validation Layer

**Purpose**: Build/test verification and completion gate.

**Current implementation**:
- `src/coding_agent/execution/verifier.py` (baseline checks)
- `src/coding_agent/execution/executor.py` (command + validate_command + repair loop)

**Integration points**:
- baseline check execution
- per-task validation command
- failure classification and retries

---

## 2.11 Memory / Context Management Layer

**Purpose**: Maintain task and project context.

**Current implementation**:
- `src/coding_agent/state_store.py` (run records)
- `src/coding_agent/presentation/chat_service.py` (session memory)

**Integration points**:
- `.agent_state/*.json`
- in-memory chat sessions (bounded history)

---

## 2.12 Security & Governance Layer

**Purpose**: Enforce policy, integrity, and safe transitions.

**Current implementation**:
- `src/coding_agent/governance/safety.py`
- `src/coding_agent/governance/integrity.py`
- `src/coding_agent/governance/lifecycle.py`

**Integration points**:
- command block list
- HMAC-signed checkpoint envelopes + key rotation
- guarded lifecycle state transitions
- approval tokens for destructive operations

---

## 3) New Structural Additions (for Clean Layering)

### 3.1 Layer Contracts Package

Added:
- `src/coding_agent/layers/contracts.py`
- `src/coding_agent/layers/mapping.py`
- `src/coding_agent/layers/__init__.py`

These provide:
- explicit architecture contracts (`*Port` protocols)
- shared DTOs (`PlanStep`, `SearchHit`, `ToolCall`, `ExecutionResult`)
- current layer-to-module mapping inventory

### 3.2 Composition Root

Added:
- `src/coding_agent/composition.py`

Purpose:
- one place to compose runtime components
- clear visibility of what layer is implemented vs roadmap
- runtime mode wiring (`safe|auto|full`) and optional provider registration

### 3.4 New Governance/Capability Components

Added:
- `src/coding_agent/tools/capabilities.py`
- `src/coding_agent/tools/doctor.py`
- `src/coding_agent/tools/advisor.py`
- `src/coding_agent/tools/approval_tokens.py`

Purpose:
- dynamic self-description (`/tools`, `/capabilities`, `/doctor`, `/status`)
- approval-token workflow for destructive actions
- operational improvement guidance based on actual runtime

### 3.3 Compatibility shims

Backward-compatible modules are intentionally retained at top-level paths (for example `src/coding_agent/web_app.py`, `src/coding_agent/agent.py`) and re-export moved implementations. This preserves existing CLI/task/test imports while enabling layered folder organization.

---

## 4) Clean Folder Intent

Recommended mental model:

- `web_app.py`, `templates/` -> **Presentation/UI**
- `agent.py` -> **Orchestration**
- `repo_intel.py`, `planner.py` -> **Analysis/Planning**
- `executor.py`, `task_graph.py`, `repair.py` -> **Execution/Validation**
- `command_runner.py`, `safety.py` -> **Tooling/Sandbox policy**
- `state_store.py`, `integrity.py`, `lifecycle.py` -> **State/Governance**
- `observability.py`, `reporting.py` -> **Telemetry/Output**
- `layers/`, `composition.py` -> **Architecture contracts + wiring**

---

## 5) Integration Strategy for Future Expansion

## 5.0 Current UI/API additions

- `/guide` for end-user operating guide and roadmap
- `/api/acceptance/run`, `/api/acceptance/report` one-click acceptance flow
- `/api/index/rebuild` semantic index refresh
- `/api/approvals/*` approval request/approve/list workflow

## 5.1 LLM Provider Integration

Implement `ReasoningEnginePort` adapter per provider:
- OpenAI/Azure/OpenRouter adapter classes
- register active provider via config
- keep orchestrator provider-agnostic

## 5.2 RAG/Code Search Integration

Implement `CodeSearchPort` with:
- text index adapter
- symbol index adapter
- semantic embedding adapter

## 5.3 Structured Editing Integration

Implement `CodeEditingEnginePort` with:
- AST-aware edit adapter per language
- fallback text patch adapter

## 5.4 Sandbox Hardening

Implement `SandboxExecutionPort` for:
- local subprocess (current)
- containerized executor (future)
- remote isolated worker (enterprise)

---

## 6) Current vs Target Maturity

- **Phase 1 (current)**: UI + orchestrator + repository understanding + plan + execution + validation + governance
- **Phase 2 (next)**: dedicated search/RAG and structured editing layers
- **Phase 3 (next)**: Git branch/PR automation layer
- **Phase 4 (enterprise)**: RBAC/SSO/audit/policy center/cost telemetry

### Pre-LLM integration priority sequence

1. Code search adapters + context packing limits
2. Structured editing + rollback
3. Containerized sandbox execution profile
4. Validation pipeline depth and deterministic retries
5. Governance approval gates + expanded observability schema
6. Provider contract tests, then concrete provider wiring

---

## 7) How to Use This Structure in Code Reviews

For every new feature, ask:

1. Which layer owns this responsibility?
2. Is there a layer contract to integrate through?
3. Does this bypass governance/security rules?
4. Are state transitions + observability events preserved?
5. Is execution validated and recoverable?

This keeps the codebase clean, understandable, and scalable as integration points grow.
