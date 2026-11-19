@echo off
setlocal
cd /d "%~dp0.."
if not exist ".env.pilot" (
  copy ".env.pilot.example" ".env.pilot" >nul
  echo Se creo .env.pilot desde la plantilla. Edite DATABASE_URL, SECRET_KEY y DEMO_PASSWORD antes de continuar.
)
python scripts\preparar_piloto.py --env-file .env.pilot
if errorlevel 2 pause
endlocal
