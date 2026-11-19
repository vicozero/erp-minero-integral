"""Agrega proyección 2D y coordenadas del almacén virtual.

Migración aditiva: crea el esquema ``wms``, la tabla versionada de mapas por
almacén y dos columnas nullable en ``mdm.storage_location``. No modifica
saldos ni existencias; el plano es una proyección de ubicaciones (UB-010).

Ninguna imagen puede marcarse como exacta: la restricción
``ck_location_map_no_exacto`` exige ``is_exact = false`` hasta que exista una
decisión formal y una migración aprobada.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import CreateSchema

revision = "e5f6a7b8c9d0"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None

_LABEL = "Referencial · no es plano exacto"


def upgrade() -> None:
    op.execute(CreateSchema("wms", if_not_exists=True))

    op.add_column(
        "storage_location",
        sa.Column("coord_x", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="mdm",
    )
    op.add_column(
        "storage_location",
        sa.Column("coord_y", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="mdm",
    )
    op.create_check_constraint(
        op.f("ck_storage_location_coordenadas"),
        "storage_location",
        "(coord_x IS NULL AND coord_y IS NULL) OR (coord_x IS NOT NULL AND coord_y IS NOT NULL)",
        schema="mdm",
    )
    op.create_index(
        op.f("ix_storage_location_coordenadas"),
        "storage_location",
        ["warehouse_id", "coord_x", "coord_y"],
        schema="mdm",
    )

    op.create_table(
        "location_map",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("map_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("label", sa.String(length=120), nullable=False, server_default=_LABEL),
        sa.Column("background_path", sa.String(length=255), nullable=True),
        sa.Column("background_name", sa.String(length=180), nullable=True),
        sa.Column("background_sha256", sa.String(length=64), nullable=True),
        sa.Column("is_exact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("width", sa.Numeric(precision=12, scale=4), nullable=False, server_default="1000"),
        sa.Column("height", sa.Numeric(precision=12, scale=4), nullable=False, server_default="600"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("width > 0", name=op.f("ck_location_map_width")),
        sa.CheckConstraint("height > 0", name=op.f("ck_location_map_height")),
        sa.CheckConstraint("is_exact = false", name=op.f("ck_location_map_no_exacto")),
        sa.CheckConstraint("map_version >= 1", name=op.f("ck_location_map_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location_map")),
        sa.UniqueConstraint("warehouse_id", "map_version", name=op.f("uq_location_map_version")),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["org.warehouse.id"], name=op.f("fk_location_map_warehouse_id")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["seg.app_user.id"], name=op.f("fk_location_map_created_by")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["seg.app_user.id"], name=op.f("fk_location_map_updated_by")
        ),
        schema="wms",
    )
    op.create_index(
        op.f("uq_location_map_active"),
        "location_map",
        ["warehouse_id"],
        unique=True,
        schema="wms",
        postgresql_where=sa.text("is_active"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO wms.location_map (
                id, warehouse_id, map_version, label, is_exact, width, height,
                is_active, created_at, version
            )
            SELECT gen_random_uuid(), w.id, 1, :label, FALSE, 1000, 600, TRUE, now(), 1
            FROM org.warehouse AS w
            WHERE NOT EXISTS (
                SELECT 1 FROM wms.location_map AS m WHERE m.warehouse_id = w.id
            )
            """
        ).bindparams(label=_LABEL)
    )


def downgrade() -> None:
    raise RuntimeError("Las migraciones de este proyecto son aditivas; no se permite downgrade.")
