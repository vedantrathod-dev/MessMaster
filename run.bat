@echo off
echo ====================================================
echo Starting College Mess Management System...
echo ====================================================

REM Check if Python is available in standard path or pgAdmin path
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    set "PATH=C:\Program Files\PostgreSQL\17\pgAdmin 4\python;C:\Program Files\PostgreSQL\17\pgAdmin 4\python\Scripts;%PATH%"
)

REM Initialize database if not present
if not exist instance\mess.db (
    echo Initializing database with sample data...
    python database.py --init-sample
)

echo Starting Flask Application on http://127.0.0.1:5000...
python app.py
pause
