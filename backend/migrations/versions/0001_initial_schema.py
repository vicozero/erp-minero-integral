"""Esquemas iniciales del ERP MINERO INTEGRAL.

Migración aditiva: crea los esquemas por dominio. Las tablas se crean en la
siguiente revisión de forma explícita y versionada (sin create_all).
El downgrade está bloqueado salvo autorización explícita.
"""

from __future__ import annotations

import os

import alembic.op as op
from alembic import context
from sqlalchemy.schema import CreateSchema, DropSchema

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
    if not _is_postgres():
        raise RuntimeError("Esta migración requiere PostgreSQL.")
    for schema in SCHEMAS:
        op.execute(CreateSchema(schema, if_not_exists=True))


def downgrade() -> None:
    if os.getenv("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "Downgrade bloqueado. Solo se permite con ALLOW_DESTRUCTIVE_DOWNGRADE=1."
        )
    if _is_postgres():
        for schema in reversed(SCHEMAS):
            op.execute(DropSchema(schema, if_exists=True, cascade=True))
