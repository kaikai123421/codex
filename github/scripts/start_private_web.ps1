param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:ADMIN_AUTH_ENABLED = "true"
$env:ADMIN_SESSION_MAX_AGE_HOURS = "24"
$env:WEBUI_HOST = $HostName
$env:WEBUI_PORT = "$Port"
$env:API_PORT = "$Port"
$env:SCHEDULE_ENABLED = "false"
$env:CORS_ALLOW_ALL = "false"
$env:TRUST_X_FORWARDED_FOR = "true"
$env:WEBUI_STARTUP_TIMEOUT_SECONDS = "30"

Write-Host "Starting DSA private web on http://$HostName`:$Port"
Write-Host "Admin auth is enabled. First visit will ask you to create the admin password."

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python main.py --serve-only --host $HostName --port $Port
