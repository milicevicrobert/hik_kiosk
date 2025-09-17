echo pokrecem 

if not exist "venv\Scripts\python.exe" exit /b 1

cd /d "%~dp0app\"

if not exist "admin_app.py" exit /b 1

REM Pokretanje Streamlit aplikacije provjeri direktorij
..\venv\Scripts\python.exe -m streamlit run admin_app.py