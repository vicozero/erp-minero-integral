@echo off
setlocal
cd /d "%~dp0..\backend"
echo === Servicio PostgreSQL ===
powershell -NoProfile -Command "Get-Service postgresql-x64-17 | Select-Object Name,Status,StartType | Format-Table -AutoSize"
echo === Migraciones ===
python -m alembic current
echo === Pruebas ===
python -m pytest -q
echo === Lint ===
python -m ruff check .
echo === Type check ===
python -m mypy app
endlocal
