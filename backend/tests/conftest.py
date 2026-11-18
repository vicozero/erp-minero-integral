from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "clave-de-prueba-sin-valor-real-0123456789")
os.environ.setdefault("DEMO_PASSWORD", "DemoSoloPruebas123")
os.environ.setdefault("ENV", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_demo_data  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.audit import models as audit_models  # noqa: E402,F401
from app.modules.costing import models as costing_models  # noqa: E402,F401
from app.modules.documentation import models as document_models  # noqa: E402,F401
from app.modules.identity import models as identity_models  # noqa: E402,F401
from app.modules.integrations import models as integration_models  # noqa: E402,F401
from app.modules.inventory import models as inventory_models  # noqa: E402,F401
from app.modules.maintenance import models as maintenance_models  # noqa: E402,F401
from app.modules.master_data import models as master_models  # noqa: E402,F401
from app.modules.organization import models as organization_models  # noqa: E402,F401
from app.modules.purchasing import models as purchasing_models  # noqa: E402,F401
from app.modules.requisitions import models as requisition_models  # noqa: E402,F401
from app.modules.workflow import models as workflow_models  # noqa: E402,F401

SCHEMAS = (
    "seg",
    "org",
    "mdm",
    "doc",
    "req",
    "wfl",
    "inv",
    "pur",
    "mnt",
    "cost",
    "intg",
    "aud",
)


@pytest.fixture()
def engine():
    mapping = {schema: None for schema in SCHEMAS}
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": mapping},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    session = Session(engine, autoflush=False, expire_on_commit=False, future=True)
    seed_demo_data(session)
    yield session
    session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
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


def direct_token(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}
