"""Esquema inicial del ERP MINERO INTEGRAL.

Migración aditiva: crea esquemas y tablas. El downgrade está bloqueado salvo que se
defina explícitamente ALLOW_DESTRUCTIVE_DOWNGRADE=1 en un entorno vacío.
"""

from __future__ import annotations

import os

import alembic.op as op
from alembic import context
from sqlalchemy import CreateSchema, DropSchema

from app.db.base import Base

# Importar modelos para poblar metadata.
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.costing import models as costing_models  # noqa: F401
from app.modules.documentation import models as document_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.integrations import models as integration_models  # noqa: F401
from app.modules.inventory import models as inventory_models  # noqa: F401
from app.modules.maintenance import models as maintenance_models  # noqa: F401
from app.modules.master_data import models as master_models  # noqa: F401
from app.modules.organization import models as organization_models  # noqa: F401
from app.modules.purchasing import models as purchasing_models  # noqa: F401
from app.modules.requisitions import models as requisition_models  # noqa: F401
from app.modules.workflow import models as workflow_models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

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


def _is_postgres() -> bool:
    return context.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    if _is_postgres():
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        for schema in SCHEMAS:
            op.execute(CreateSchema(schema, if_not_exists=True))
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    if os.getenv("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "Downgrade bloqueado. Solo se permite en base vacía con "
            "ALLOW_DESTRUCTIVE_DOWNGRADE=1."
        )
    tables = sorted(Base.metadata.sorted_tables, key=lambda t: (t.schema or "", t.name), reverse=True)
    for table in tables:
        op.drop_table(table.name, schema=table.schema, if_exists=True)
    if _is_postgres():
        for schema in reversed(SCHEMAS):
            op.execute(DropSchema(schema, if_exists=True, cascade=True))
