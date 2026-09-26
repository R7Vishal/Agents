# Install Details - Coding Agent (Different Machine)

This guide explains how to install and run the `coding-agent` project on another machine using VS Code.

## 1) Prerequisites on target machine

- Windows machine with PowerShell
- Python 3.10 or higher (`python --version`)
- VS Code installed
- Recommended VS Code extensions:
  - `ms-python.python`
  - `ms-python.vscode-pylance`

## 2) Export the project from source machine

From the project root (`coding-agent`), run:

```powershell
.\scripts\export-agent.ps1 -OutputZip coding-agent-portable.zip
```

This creates a portable ZIP package containing source code, VS Code configuration, scripts, examples, and docs.

## 3) Transfer to target machine

- Copy `coding-agent-portable.zip` to the target machine.
- Extract it to a folder, for example:

```text
C:\dev\coding-agent
```

- Open that extracted folder in VS Code.

## 4) Install dependencies on target machine

Open PowerShell in the extracted project root and run:

```powershell
.\scripts\install-agent.ps1 -ProjectPath . -RunTests
```

What this does:

- Creates `.venv` if missing
- Upgrades `pip`
- Installs dependencies from `requirements.txt`
- Installs project in editable mode (`pip install -e .`)
- Runs tests (when `-RunTests` is used)

## 5) Configure agent for your environment

Edit this file:

```text
.vscode/coding-agent.json
```

Important keys:

- `mode`: `first-run` | `run-plan` | `rotate-key`
- `repo`: target repository path to analyze/execute
- `output`: output report path
- `plan_file`: required for `run-plan`
- `max_repair_attempts_per_task`, `resume_*` settings for resume behavior

## 6) Run the agent

### Option A: VS Code Tasks

In VS Code:

- Open **Command Palette** -> **Tasks: Run Task**
- Run one of:
  - `Coding Agent: UI`
  - `Coding Agent: Run Config`
  - `Coding Agent: Run Config (first-run)`
  - `Coding Agent: Run Config (run-plan)`
  - `Coding Agent: Rotate Key`

### Option B: Terminal command

```powershell
coding-agent run-config --config .vscode/coding-agent.json
```

Mode override example:

```powershell
coding-agent run-config --config .vscode/coding-agent.json --mode run-plan
```

## 7) Launch the chat UI

```powershell
coding-agent-ui
```

Open in browser:

```text
http://127.0.0.1:5050
```

Guide page:

```text
http://127.0.0.1:5050/guide
```

From the UI top bar, you can run:

- **Run Acceptance** (one-click scenarios 1-8 + report open)

## 8) Verification checklist

- `python --version` shows 3.10+
- Install script completes successfully
- Tests pass (`pytest`)
- `coding-agent run-config ...` generates a report
- UI starts at `http://127.0.0.1:5050`
- Guide opens at `http://127.0.0.1:5050/guide`
- Acceptance report opens from one-click UI flow

## 9) Benchmark and acceptance scripts

Run acceptance scenarios directly:

```powershell
python .\scripts\run_acceptance_scenarios.py
```

Run Copilot parity benchmark:

```powershell
python .\scripts\run_copilot_parity_benchmark.py
```

Outputs:

- `reports/acceptance-scenarios-report.md`
- `reports/copilot-parity-benchmark.md`

## 10) Troubleshooting

### Issue: editable install fails with file lock (`WinError 32`)

Cause: a running process (often `coding-agent-ui.exe`) is locking files in `.venv\Scripts`.

Fix:

1. Close running agent UI and Python terminals
2. Re-run:

```powershell
.\scripts\install-agent.ps1 -ProjectPath .
```

### Issue: command not found (`coding-agent` / `coding-agent-ui`)

Use venv-local executables directly:

```powershell
.\.venv\Scripts\coding-agent run-config --config .vscode/coding-agent.json
.\.venv\Scripts\coding-agent-ui
```

### Issue: wrong repository analyzed

Update `repo` in `.vscode/coding-agent.json` to the correct path and rerun.

## 11) Recommended first run

On a new machine, start with:

```powershell
coding-agent run-config --config .vscode/coding-agent.json --mode first-run
```

Then switch to `run-plan` after validating baseline behavior.
