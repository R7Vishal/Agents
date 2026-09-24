param(
    [string]$ProjectPath = "."
)

$ErrorActionPreference = "Stop"

Push-Location $ProjectPath
try {
    python -m pytest -q tests\test_reasoning_provider_contract.py tests\test_reasoning_gateway_fallback.py tests\test_reasoning_router.py
}
finally {
    Pop-Location
}
