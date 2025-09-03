@echo off
title Pokretanje Kiosk Sustava (NiceGUI + Skener)

echo Aktiviram virtualno okruženje...
call venv\Scripts\activate

echo Pokrećem NiceGUI kiosk (main_kiosk.py)...
start "" cmd /k "cd /d app\niceGui && python main_kiosk.py"

echo Pokrećem alarm skener (alarm_scaner.py)...
start "" cmd /k "cd /d app\axpro && python alarm_scaner.py"

echo NiceGUI kiosk pokrenut na portu 8080, alarm skener aktiviran.
pause
