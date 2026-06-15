$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

Set-Location $Backend
$env:PYTHONPATH = $Backend

if (-not $env:DATABASE_URL) {
    $LocalData = Join-Path $Root "data\dev"
    New-Item -ItemType Directory -Force -Path $LocalData | Out-Null
    $SqlitePath = (Join-Path $LocalData "debugsql.sqlite").Replace("\", "/")
    $env:DATABASE_URL = "sqlite:///$SqlitePath"
}

if (-not $env:DEBUGSQL_AUTO_LOGIN) {
    $env:DEBUGSQL_AUTO_LOGIN = "1"
}

$BenchmarkDataDir = Join-Path $Root "data\benchmarks"
$env:BENCHMARK_DATA_DIR = $BenchmarkDataDir
$env:BENCHMARK_HOST_DATA_DIR = $BenchmarkDataDir

if (-not (Test-Path $Python)) {
    Write-Error "Backend virtual environment was not found at $Python. Create it in PyCharm or run: python -m venv .venv"
    exit 1
}

& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Error "Database migration failed. Fix the error above before starting the backend."
    exit $LASTEXITCODE
}

& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
