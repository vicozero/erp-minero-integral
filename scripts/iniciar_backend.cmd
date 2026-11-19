@echo off
setlocal
cd /d "%~dp0..\backend"
echo Iniciando ERP MINERO INTEGRAL en http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal
