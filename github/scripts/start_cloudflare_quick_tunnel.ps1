param(
    [string]$Url = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cloudflared) {
    $cloudflaredPath = $cloudflared.Source
} else {
    $cloudflaredPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
}

if (-not (Test-Path $cloudflaredPath)) {
    Write-Error "cloudflared is not installed. Install Cloudflare Tunnel first, then rerun this script."
}

Write-Host "Opening a free Cloudflare quick tunnel to $Url"
Write-Host "Keep this window open while you need remote access."
Write-Host "The DSA app still requires its admin password."

& $cloudflaredPath tunnel --protocol http2 --url $Url
