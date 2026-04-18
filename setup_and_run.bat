
---

# ✅ `setup_and_run.bat`

```bat id="b8n4zp"
@echo off
title Tournament Manager Setup

echo ============================================
echo      TOURNAMENT MANAGER - Setup ^& Run
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/3] Installing Python packages...
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org flask flask-socketio flask-cors pyjwt simple-websocket

if errorlevel 1 (
    echo [WARN] pip install had issues. Trying with requirements.txt...
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
)

echo.
echo [2/3] Initializing database...
python -c "from database import init_db; init_db(); print('Database ready!')"

echo.
echo [3/3] Starting server...
echo.
echo ============================================
echo Server: http://localhost:5000
echo Admin:  http://localhost:5000/admin/login
echo Login:  admin / admin123
echo ============================================

python app.py
pause