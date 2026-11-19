@echo off
setlocal
cd /d "%~dp0.."
python scripts\portal_ctl.py stop
endlocal
