param(
    [string]$ProjectPath = ".",
    [ValidateSet("ui", "run-config")]
    [string]$Mode = "ui",
    [switch]$RunTests
)

$ErrorActionPreference = "Stop"

$target = Resolve-Path $ProjectPath
Set-Location $target

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Message
    }
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StepName
    )

    Write-Host "[setup-run] $StepName"
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $StepName (exit code $LASTEXITCODE)"
    }
}

Assert-Command -Name "python" -Message "Python is required. Install Python 3.10+ and ensure 'python' is on PATH."

$pythonVersionText = (& python --version) 2>&1
Write-Host "[setup-run] Detected $pythonVersionText"

$versionRaw = ($pythonVersionText -replace "Python", "").Trim()
$pyVersion = [version]$versionRaw
if ($pyVersion -lt [version]"3.10") {
    throw "Python 3.10+ is required. Current: $pyVersion"
}

#$installScript = Join-Path $target "scripts\install-agent.ps1"
$installScript = Join-Path $PSScriptRoot "install-agent.ps1"
if (-not (Test-Path $installScript)) {
    throw "Install script not found: $installScript"
}

$installArgs = @("-ExecutionPolicy", "Bypass", "-File", $installScript, "-ProjectPath", ".")
if ($RunTests) {
    $installArgs += "-RunTests"
}
Invoke-Step -Command "powershell" -Arguments $installArgs -StepName "Install project prerequisites"

$uiExe = Join-Path $target ".venv\Scripts\coding-agent-ui"
$agentExe = Join-Path $target ".venv\Scripts\coding-agent"

if ($Mode -eq "ui") {
    if (-not (Test-Path "$uiExe.exe") -and -not (Test-Path $uiExe)) {
        throw "UI executable not found in .venv\Scripts"
    }

    Write-Host "[setup-run] Starting UI at http://127.0.0.1:5050"
    & $uiExe
    exit $LASTEXITCODE
}

if ($Mode -eq "run-config") {
    if (-not (Test-Path "$agentExe.exe") -and -not (Test-Path $agentExe)) {
        throw "Agent executable not found in .venv\Scripts"
    }

    $configPath = Join-Path $target ".vscode\coding-agent.json"
    if (-not (Test-Path $configPath)) {
        throw "Config file not found: $configPath"
    }

    Invoke-Step -Command $agentExe -Arguments @("run-config", "--config", ".vscode/coding-agent.json") -StepName "Run configured workflow"
}
