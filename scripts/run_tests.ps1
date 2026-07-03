# Change location to the repo root (this script now lives in scripts/)
Set-Location (Split-Path $PSScriptRoot -Parent)

# Set PYTHONPATH to include the project root
$env:PYTHONPATH = ".;$env:PYTHONPATH"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "1. Running Pytest Unit Tests..." -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
& .venv/Scripts/pytest -v

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "2. Running Verification Scripts..." -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

Write-Host "`n[Identity Verification]" -ForegroundColor Yellow
& .venv/Scripts/python tests/verify_identity.py

Write-Host "`n[Metrics Backend Verification]" -ForegroundColor Yellow
& .venv/Scripts/python tests/verify_metrics.py

Write-Host "`n[Ramachandran Verification]" -ForegroundColor Yellow
& .venv/Scripts/python tests/verify_ramachandran.py

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "Verification Run Complete!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
