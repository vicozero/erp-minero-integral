from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DEFAULT_ENV_FILE = ROOT / ".env.pilot"
PILOT_DATABASE_NAME = "erp_minero_pilot"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def connection_params(database_url: str) -> dict[str, object]:
    parts = urlsplit(database_url)
    if parts.scheme != "postgresql+psycopg":
        raise ValueError("DATABASE_URL debe usar postgresql+psycopg")
    userinfo = parts.netloc.rsplit("@", 1)[0]
    username, password = userinfo.split(":", 1)
    database = parts.path.lstrip("/")
    if database != PILOT_DATABASE_NAME:
        raise ValueError(
            f"El perfil piloto debe apuntar a {PILOT_DATABASE_NAME}; se recibió {database!r}."
        )
    return {
        "host": parts.hostname or "127.0.0.1",
        "port": parts.port or 5432,
        "dbname": database,
        "user": unquote(username),
        "password": unquote(password),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara la base sintética del piloto sin crear bases.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--skip-seed", action="store_true", help="Solo aplica migraciones.")
    args = parser.parse_args()

    env_file = args.env_file if args.env_file.is_absolute() else ROOT / args.env_file
    values = load_env_file(env_file)
    database_url = values.get("DATABASE_URL")
    if not database_url or "<password>" in database_url:
        print(f"ERROR: configure DATABASE_URL en {env_file} antes de continuar.")
        return 2
    try:
        params = connection_params(database_url)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"Verificando conexión a {PILOT_DATABASE_NAME}…")
    try:
        with psycopg.connect(**params) as connection:  # type: ignore[arg-type]
            with connection.cursor() as cursor:
                cursor.execute("select current_database(), current_user")
                print("Conexión correcta:", cursor.fetchone())
    except psycopg.OperationalError:
        print(
            "ERROR: la base no existe o no es accesible. Un administrador debe crearla:\n"
            f'  CREATE DATABASE {PILOT_DATABASE_NAME} OWNER erp_minero_app;\n'
            "Este script no crea bases ni solicita CREATEDB al rol de aplicación."
        )
        return 2

    env = os.environ.copy()
    env["ERP_ENV_FILE"] = str(env_file)
    for key, value in values.items():
        env.setdefault(key, value)

    def run(command: list[str], label: str) -> bool:
        print(f"{label}…")
        result = subprocess.run(command, cwd=BACKEND_DIR, env=env, check=False)
        if result.returncode != 0:
            print(f"ERROR: {label} terminó con código {result.returncode}.")
            return False
        return True

    if not run([sys.executable, "-m", "alembic", "upgrade", "head"], "Aplicando migraciones"):
        return 1
    if not run([sys.executable, "-m", "alembic", "current"], "Revisión activa"):
        return 1
    if not args.skip_seed:
        seed_command = [
            sys.executable,
            "-c",
            "import app.main; from app.db.seed import seed_demo_data; "
            "from app.db.session import SessionLocal; db = SessionLocal(); seed_demo_data(db); "
            "db.close(); print('Datos sintéticos del piloto listos')",
        ]
        if not run(seed_command, "Sembrando datos sintéticos"):
            return 1

    print("Preparación del piloto completada. No se modificaron otras bases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
