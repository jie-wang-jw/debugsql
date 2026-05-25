$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Frontend = Join-Path $Root "frontend"

Set-Location $Frontend
$env:VITE_DEV_API_TARGET = "http://127.0.0.1:8000"

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    npm install
}

npm run dev -- --host 127.0.0.1
