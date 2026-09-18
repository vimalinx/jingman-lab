@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
if not exist ".venv\Scripts\python.exe" (
 echo Python environment missing. Run setup-windows.cmd first.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" "tools\windows.py" start
if errorlevel 1 pause
