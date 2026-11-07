$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Invoke-Checked {
    param([string]$Command, [string[]]$CommandArgs)
    & $Command @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "$Command failed (exit $LASTEXITCODE)" }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker was not found. Install and start Docker Desktop, reopen PowerShell, then run this script again.'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create .venv with Python 3.12 and install requirements.txt first.'
}

$previousDatabase = $env:DATABASE_URL
$previousTestDatabase = $env:TEST_DATABASE_URL
Push-Location -LiteralPath $projectRoot
try {
    Invoke-Checked 'docker' @('compose', 'up', '-d', '--wait')
    $exists = Invoke-Checked 'docker' @('compose', 'exec', '-T', 'postgres', 'psql', '-U', 'sentrix', '-d', 'postgres', '-tAc', "SELECT 1 FROM pg_database WHERE datname='sentrix_test'")
    if (($exists | Out-String).Trim() -ne '1') {
        Invoke-Checked 'docker' @('compose', 'exec', '-T', 'postgres', 'createdb', '-U', 'sentrix', 'sentrix_test')
    }

    # Only the disposable database is migrated or cleaned by this verification.
    $env:TEST_DATABASE_URL = 'postgresql+psycopg://sentrix:local-only@localhost:5432/sentrix_test'
    $env:DATABASE_URL = $env:TEST_DATABASE_URL
    Invoke-Checked $python @('-m', 'alembic', 'upgrade', 'head')
    Invoke-Checked $python @('-m', 'alembic', 'check')

    # Keep the safety guard's working database separate from the test target.
    $env:DATABASE_URL = 'sqlite:///./demo.db'
    Invoke-Checked $python @('-m', 'pytest', '-q', '--basetemp=.tmp/pytest-postgres')
    Write-Host 'Postgres migration, schema, API, rollback, persistence, and concurrency checks passed.'
} finally {
    $env:DATABASE_URL = $previousDatabase
    $env:TEST_DATABASE_URL = $previousTestDatabase
    Pop-Location
}
