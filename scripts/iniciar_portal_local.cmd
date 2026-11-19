@echo off
setlocal
cd /d "%~dp0.."
echo Compilando y iniciando el portal local en http://127.0.0.1:8080
python scripts\portal_ctl.py start --build
if errorlevel 1 pause
endlocal
