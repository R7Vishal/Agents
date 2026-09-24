param(
    [string]$OutputZip = "coding-agent-portable.zip"
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$zipPath = Join-Path $projectRoot $OutputZip

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

$staging = Join-Path $projectRoot ".export_staging"
if (Test-Path $staging) {
    Remove-Item $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null

$exclude = @(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".agent_state",
    ".agent_logs",
    ".export_staging",
    "node_modules"
)

$children = Get-ChildItem -Path $projectRoot -Force
foreach ($child in $children) {
    $name = $child.Name

    if ($exclude -contains $name) {
        continue
    }

    if ($name -eq $OutputZip) {
        continue
    }

    $destination = Join-Path $staging $name
    Copy-Item $child.FullName -Destination $destination -Recurse -Force
}

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force
Remove-Item $staging -Recurse -Force

Write-Host "Export completed: $zipPath"
