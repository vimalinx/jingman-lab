@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
 py -3 -m venv .venv
 if errorlevel 1 (
  echo Install Python 3.10 or newer first, then run this file again.
  pause
  exit /b 1
 )
)
".venv\Scripts\python.exe" -m pip install -r requirements-test.txt -r requirements-integrations.txt -r requirements-import.txt
if errorlevel 1 (
 pause
 exit /b 1
)
call start.cmd
