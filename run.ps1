# PowerShell runner for College Mess Management System
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Starting College Mess Management System..." -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Cyan

# Ensure Python is reachable
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    $env:PATH = "C:\Program Files\PostgreSQL\17\pgAdmin 4\python;C:\Program Files\PostgreSQL\17\pgAdmin 4\python\Scripts;" + $env:PATH
}

# Check database
if (-not (Test-Path "instance\mess.db")) {
    Write-Host "Initializing database with sample records..." -ForegroundColor Yellow
    python database.py --init-sample
}

Write-Host "Launching server at http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "Default Admin: admin | admin123" -ForegroundColor Yellow
python app.py
