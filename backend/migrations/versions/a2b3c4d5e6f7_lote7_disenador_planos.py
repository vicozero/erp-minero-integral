"""Agrega planos editables 2D/3D con borrador y versiones publicadas.

Migración aditiva: crea ``wms.floor_plan``. No modifica ``wms.location_map``,
``mdm.storage_location`` ni saldos. Un único array JSON de elementos es la
fuente de la escena compartida por 2D y 3D; las versiones publicadas se
conservan y el borrador se publica sin sobrescribir la versión activa.

La geometría es referencial por defecto (``dimensions_verified = false``).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a2b3c4d5e6f7"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

_LABEL = "Referencial · no es plano exacto"


def upgrade() -> None:
    op.create_table(
        "floor_plan",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("label", sa.String(length=120), nullable=False, server_default=_LABEL),
        sa.Column("width", sa.Numeric(precision=12, scale=4), nullable=False, server_default="1000"),
        sa.Column("height", sa.Numeric(precision=12, scale=4), nullable=False, server_default="600"),
        sa.Column("grid_size", sa.Numeric(precision=12, scale=4), nullable=False, server_default="20"),
        sa.Column("scale_label", sa.String(length=40), nullable=True),
        sa.Column("dimensions_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("elements", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("location_refs", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("background_path", sa.String(length=255), nullable=True),
        sa.Column("background_name", sa.String(length=180), nullable=True),
        sa.Column("background_sha256", sa.String(length=64), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("width > 0", name=op.f("ck_floor_plan_width")),
        sa.CheckConstraint("height > 0", name=op.f("ck_floor_plan_height")),
        sa.CheckConstraint("grid_size > 0", name=op.f("ck_floor_plan_grid_size")),
        sa.CheckConstraint("plan_version >= 1", name=op.f("ck_floor_plan_version")),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_floor_plan_revision")),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','ARCHIVED')", name=op.f("ck_floor_plan_status")
        ),
        sa.CheckConstraint("jsonb_typeof(elements) = 'array'", name=op.f("ck_floor_plan_elements")),
        sa.CheckConstraint("jsonb_typeof(location_refs) = 'array'", name=op.f("ck_floor_plan_refs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan")),
        sa.UniqueConstraint("warehouse_id", "plan_version", name=op.f("uq_floor_plan_version")),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["org.warehouse.id"], name=op.f("fk_floor_plan_warehouse_id")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["seg.app_user.id"], name=op.f("fk_floor_plan_created_by")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["seg.app_user.id"], name=op.f("fk_floor_plan_updated_by")
        ),
        sa.ForeignKeyConstraint(
            ["published_by"], ["seg.app_user.id"], name=op.f("fk_floor_plan_published_by")
        ),
        schema="wms",
    )
    op.create_index(
        op.f("uq_floor_plan_active"),
        "floor_plan",
        ["warehouse_id"],
        unique=True,
        schema="wms",
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        op.f("uq_floor_plan_draft"),
        "floor_plan",
        ["warehouse_id"],
        unique=True,
        schema="wms",
        postgresql_where=sa.text("status = 'DRAFT'"),
    )


def downgrade() -> None:
    raise RuntimeError("Las migraciones de este proyecto son aditivas; no se permite downgrade.")
