from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR.parent / ".env"
TEST_DATABASE_NAME = "erp_minero_test"


def _load_env_file() -> dict[str, str]:
    """Lee el .env local sin imprimir ni versionar credenciales.

    En CI no existe `.env`: las variables se proveen explícitamente desde el
    workflow. La ausencia del archivo no debe impedir ejecutar las pruebas.
    """
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_env_values = _load_env_file()
# El entorno puede seleccionar un clúster PostgreSQL efímero para validar sin
# depender del servicio local (por ejemplo, durante una ventana de mantenimiento).
# Los valores del .env se usan sólo si no fueron provistos explícitamente.
for _key in ("DATABASE_URL", "SECRET_KEY", "DEMO_PASSWORD"):
    if _key in _env_values and _key not in os.environ:
        os.environ[_key] = _env_values[_key]

# Las pruebas jamás deben apuntar a la base de desarrollo. La URL se deriva
# de la configuración real, cambiando únicamente el nombre de la base.
_parts = urlsplit(os.environ["DATABASE_URL"])
os.environ["DATABASE_URL"] = urlunsplit(
    (_parts.scheme, _parts.netloc, f"/{TEST_DATABASE_NAME}", _parts.query, _parts.fragment)
)
os.environ["ENV"] = "test"
os.environ.setdefault("DEMO_PASSWORD", "DemoSoloPruebas123")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.seed import seed_demo_data  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


def reset_test_database(engine: Engine) -> None:
    """Limpia y vuelve a sembrar la base sintética de pruebas.

    Solo se usa sobre `erp_minero_test`; nunca sobre la base de desarrollo ni
    sobre datos reales. Garantiza que las pruebas que confirman transacciones
    no contaminen a las que usan transacciones revertidas.
    """
    from sqlalchemy.orm import Session as SessionClass

    from app.db.seed import seed_demo_data

    schemas = ("seg", "org", "mdm", "doc", "req", "wfl", "inv", "pur", "mnt", "cost", "intg", "aud", "wms")
    session = SessionClass(engine, expire_on_commit=False)
    try:
        database = session.execute(text("SELECT current_database()")).scalar_one()
        if database != TEST_DATABASE_NAME:
            raise RuntimeError(f"El reset de pruebas requiere {TEST_DATABASE_NAME}, obtuvo {database}")

        schema_list = ", ".join(f"'{schema}'" for schema in schemas)
        tables = [
            row[0]
            for row in session.execute(
                text(
                    "SELECT schemaname || '.' || tablename FROM pg_tables "
                    f"WHERE schemaname IN ({schema_list})"
                )
            )
        ]
        if tables:
            # B.1 protege inv.stock_movement contra TRUNCATE accidental. El arnés
            # de pruebas es el único habilitado para limpiar la base sintética,
            # y lo hace con una bandera local a esta transacción.
            session.execute(text("SET LOCAL inv.allow_maintenance_truncate = 'on'"))
            session.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        seed_demo_data(session)
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="session", autouse=True)
def _reset_database_once(engine: Engine) -> Generator[None, None, None]:
    """Restablece la base de pruebas una vez al inicio de la sesión."""
    reset_test_database(engine)
    yield


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Motor PostgreSQL real. Aplica migraciones antes de cualquier prueba."""
    from app.core.config import settings

    if not settings.DATABASE_URL.startswith("postgresql+psycopg://"):
        raise RuntimeError("Las pruebas requieren PostgreSQL real.")

    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(alembic_config, "head")

    eng = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    with eng.connect() as connection:
        database = connection.execute(text("SELECT current_database()")).scalar_one()
        if database != TEST_DATABASE_NAME:
            raise RuntimeError(f"Base de pruebas inesperada: {database}")

    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine: Engine) -> Generator[Session, None, None]:
    """Sesión aislada: todo se revierte al terminar la prueba."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )
    try:
        seed_demo_data(session)
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_header(client: TestClient, username: str = "demo.admin") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": os.environ["DEMO_PASSWORD"]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def login_with_cookie(
    client: TestClient,
    username: str = "demo.admin",
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Inicia sesión usando cookies reales y devuelve la cabecera CSRF."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": os.environ["DEMO_PASSWORD"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def clear_session(client: TestClient) -> None:
    client.cookies.clear()
