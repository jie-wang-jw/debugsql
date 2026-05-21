$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

Set-Location $Backend
$env:PYTHONPATH = $Backend

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql+psycopg://debugsql:debugsql_dev_password@127.0.0.1:5432/debugsql"
}

if (-not $env:DEBUGSQL_AUTO_LOGIN) {
    $env:DEBUGSQL_AUTO_LOGIN = "1"
}

if (-not (Test-Path $Python)) {
    Write-Error "Backend virtual environment was not found at $Python. Create it in PyCharm or run: python -m venv .venv"
    exit 1
}

& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
