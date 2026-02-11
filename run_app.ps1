<#
  Quick launcher for the Job Tracker app on Windows.

  Usage (from PowerShell):
    cd "C:\Projects\MCP Server\job-tracker"
    .\run_app.ps1
  Or double-click it in Explorer and choose "Run with PowerShell".
#>

$ErrorActionPreference = "Stop"

# Go to script directory
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "== Job Tracker launcher ==" -ForegroundColor Cyan

# Ensure virtual environment exists
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (venv)..." -ForegroundColor Yellow
    python -m venv venv

    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    .\venv\Scripts\python.exe -m pip install --upgrade pip
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
}

# Optional: quick check that Docker/Postgres is likely up
try {
    $tcp = Test-NetConnection -ComputerName "localhost" -Port 5432 -WarningAction SilentlyContinue
    if (-not $tcp.TcpTestSucceeded) {
        Write-Host "WARNING: PostgreSQL (port 5432) does not appear to be reachable." -ForegroundColor Yellow
        Write-Host "Make sure your Docker/Postgres container is running before using the app." -ForegroundColor Yellow
    }
} catch {
    # Ignore if Test-NetConnection not available
}

Write-Host "Starting Flask app..." -ForegroundColor Green
$env:PYTHONIOENCODING = "utf-8"

.\venv\Scripts\python.exe run.py

