@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" tools\phone.py stop
set PYTHONUTF8=1
".venv\Scripts\python.exe" "tools\windows.py" stop
pause
