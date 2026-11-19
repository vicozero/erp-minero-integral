@echo off
setlocal
cd /d "%~dp0.."
python scripts\verificar_portal.py
if errorlevel 1 pause
endlocal
