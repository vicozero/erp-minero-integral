@echo off
setlocal
cd /d "%~dp0..\backend"
echo Sembrando datos sinteticos en la base de desarrollo.
python -c "import app.main; from app.db.seed import seed_demo_data; from app.db.session import SessionLocal; db = SessionLocal(); seed_demo_data(db); db.close(); print('Datos demo sinteticos listos')"
endlocal
