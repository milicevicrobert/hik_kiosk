@echo off

if not exist "venv\Scripts\python.exe" exit /b 1

cd /d "%~dp0axpro"

if not exist "alarm_scanner.py" exit /b 1

..\venv\Scripts\python.exe alarm_scanner.py