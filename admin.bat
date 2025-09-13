@echo off

if not exist "venv\Scripts\python.exe" exit /b 1

cd /d "%~dp0app\streamlit"

if not exist "admin_app.py" exit /b 1

..\..\venv\Scripts\python.exe -m streamlit run admin_app.py