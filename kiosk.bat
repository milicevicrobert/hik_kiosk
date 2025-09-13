@echo off

if not exist "venv\Scripts\python.exe" exit /b 1

cd /d "%~dp0app\niceGui"

if not exist "main_kiosk.py" exit /b 1

..\..\venv\Scripts\python.exe main_kiosk.py