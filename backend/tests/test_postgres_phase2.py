from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.organization.models import Company, Warehouse

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_conexion_postgresql_real(engine) -> None:
    """La conexión usa PostgreSQL local, rol no superusuario y parámetros seguros."""
    with engine.connect() as connection:
        user, database, version = connection.execute(
            text("SELECT current_user, current_database(), version()")
        ).one()
        timezone, encoding = connection.execute(
            text("SELECT current_setting('TimeZone'), current_setting('server_encoding')")
        ).one()
        is_superuser = connection.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()

    assert database == "erp_minero_test"
    assert user == "erp_minero_app"
    assert is_superuser is False
    assert "PostgreSQL 17" in version
    assert timezone == "America/Mexico_City"
    assert encoding == "UTF8"


def test_migraciones_y_tipos_de_datos(engine) -> None:
    """Alembic dejó el esquema versionado con TIMESTAMPTZ y NUMERIC, nunca FLOAT."""
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
        schemas = set(connection.execute(text("SELECT nspname FROM pg_namespace")).scalars())
        domain_tables = connection.execute(
            text(
                "SELECT count(*) FROM pg_tables "
                "WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'public')"
            )
        ).scalar_one()
        created_at_types = set(
            connection.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE column_name = 'created_at' AND table_schema NOT IN ('pg_catalog', 'information_schema')"
                )
            ).scalars()
        )
        float_columns = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE data_type IN ('double precision', 'real') "
                "AND table_schema NOT IN ('pg_catalog', 'information_schema')"
            )
        ).scalar_one()

    assert revision in {"d147e7ec92fb", "f3a9c1d7b2e4", "f4a7c1e2b3d6", "a1b2c3d4e5f6"}
    assert {"seg", "org", "mdm", "doc", "req", "wfl", "inv", "pur", "mnt", "cost", "intg", "aud"} <= schemas
    assert domain_tables >= 37
    assert created_at_types == {"timestamp with time zone"}
    assert float_columns == 0

    with engine.connect() as connection:
        wms_tables = set(
            connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'mdm' AND tablename IN "
                    "('item_family','item_uom_conversion','item_cross_reference',"
                    "'item_supplier','storage_location','location_restriction','lot','serial')"
                )
            ).scalars()
        )
        assert len(wms_tables) == 8
        new_columns = set(
            connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'inv' AND table_name = 'stock_balance' "
                    "AND column_name IN ('lot_ref_id','location_ref_id')"
                )
            ).scalars()
        )
        assert new_columns == {"lot_ref_id", "location_ref_id"}


def test_crud_ficticio_en_postgresql(db: Session) -> None:
    """Alta, lectura, modificación y borrado de un registro sintético."""
    code = f"QA-{uuid.uuid4().hex[:8]}"
    company = Company(code=code, name="Compañía sintética QA")
    db.add(company)
    db.flush()

    assert db.execute(select(Company).where(Company.code == code)).scalar_one() is company

    company.name = "Compañía sintética QA actualizada"
    db.flush()
    db.refresh(company)
    assert company.name == "Compañía sintética QA actualizada"

    db.delete(company)
    db.flush()
    assert db.execute(select(Company).where(Company.code == code)).scalar_one_or_none() is None


def test_foreign_key_invalida(db: Session) -> None:
    """Una relación con.company_id inexistente es rechazada por PostgreSQL."""
    warehouse = Warehouse(
        company_id=uuid.uuid4(),
        code="ALM-INVALIDO",
        name="Almacén sintético inválido",
        warehouse_type="MAIN",
    )
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(warehouse)
            db.flush()


def test_obligatorios_y_unicos(db: Session) -> None:
    """NOT NULL y UNIQUE se enforcing en la base, no solo en la aplicación."""
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Company(code=f"NN-{uuid.uuid4().hex[:6]}", name=None))  # type: ignore[arg-type]
            db.flush()

    code = f"UQ-{uuid.uuid4().hex[:6]}"
    db.add(Company(code=code, name="Primera compañía sintética"))
    db.flush()

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Company(code=code, name="Compañía sintética duplicada"))
            db.flush()


def test_rollback_descarta_cambios(db: Session) -> None:
    """Un rollback explícito deja la base sin rastro de la escritura."""
    marker = f"RB-{uuid.uuid4().hex[:8]}"
    with pytest.raises(RuntimeError, match="cancelado"):
        with db.begin_nested():
            db.add(Company(code=marker, name="Escritura que debe revertirse"))
            db.flush()
            raise RuntimeError("cancelado a propósito")

    assert db.execute(select(Company.id).where(Company.code == marker)).scalar_one_or_none() is None


def test_health_endpoints_y_openapi(client) -> None:
    """Los endpoints de salud responden y no filtran credenciales."""
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    health_db = client.get("/health/db")
    assert health_db.status_code == 200
    assert health_db.json() == {"status": "ok", "database": "postgresql"}

    schema = client.get("/openapi.json").json()
    assert "/health" in schema["paths"]
    assert "/health/db" in schema["paths"]
    assert "password" not in health_db.text.lower()


def test_no_hay_credenciales_versionadas() -> None:
    """El .env real está ignorado y ningún archivo versionado contiene sus secretos."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert ".env" not in tracked

    ignored = subprocess.run(
        ["git", "check-ignore", ".env"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert ignored.returncode == 0

    env_values: dict[str, str] = {}
    for raw_line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env_values[key.strip()] = value.strip().strip('"').strip("'")

    secrets = {env_values["SECRET_KEY"]}
    db_password = urlsplit(env_values["DATABASE_URL"]).password
    if db_password:
        secrets.add(db_password)

    for relative_path in tracked:
        path = REPO_ROOT / relative_path
        if not path.is_file() or path.suffix not in {".py", ".md", ".toml", ".ini", ".example", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for secret in secrets:
            assert secret not in content, f"Secreto presente en {relative_path}"

    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "<password>" in example
