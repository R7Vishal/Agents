param(
    [string]$ProjectPath = ".",
    [switch]$RunTests
)

$ErrorActionPreference = "Stop"

$target = Resolve-Path $ProjectPath
Set-Location $target

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StepName
    )

    Write-Host "[install] $StepName"
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $StepName (exit code $LASTEXITCODE)"
    }
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = Join-Path $target ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment python not found at $python"
}

Invoke-Step -Command $python -Arguments @("-m", "pip", "install", "--upgrade", "pip") -StepName "Upgrade pip"
Invoke-Step -Command $python -Arguments @("-m", "pip", "install", "-r", "requirements.txt") -StepName "Install requirements"

try {
    Invoke-Step -Command $python -Arguments @("-m", "pip", "install", "-e", ".") -StepName "Install editable package"
} catch {
    throw "Editable install failed. Ensure no running process is locking scripts (e.g., close coding-agent-ui / Python terminals) and retry. Details: $($_.Exception.Message)"
}

if ($RunTests) {
    Invoke-Step -Command $python -Arguments @("-m", "pytest", "-q") -StepName "Run tests"
}

Write-Host "Installation completed in $target"
Write-Host "Run UI with: .venv\Scripts\coding-agent-ui"
Write-Host "Run config mode with: .venv\Scripts\coding-agent run-config --config .vscode/coding-agent.json"
