"""Agrega tablas del módulo documental: plantillas, renders y vales de salida.

La migración es aditiva: crea tablas nuevas en ``doc`` y no modifica ni
elimina datos existentes. ``downgrade()`` falla deliberadamente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b7c8d9e0f1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_template",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("document_type_code", sa.String(length=20), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("page_width_pt", sa.Numeric(8, 2), nullable=False),
        sa.Column("page_height_pt", sa.Numeric(8, 2), nullable=False),
        sa.Column("orientation", sa.String(length=12), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "orientation IN ('LANDSCAPE','PORTRAIT')", name=op.f("ck_document_template_orientation")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_template")),
        sa.UniqueConstraint("code", "template_version", name=op.f("uq_document_template_version")),
        sa.ForeignKeyConstraint(["created_by"], ["seg.app_user.id"], name=op.f("fk_document_template_created_by")),
        sa.ForeignKeyConstraint(["updated_by"], ["seg.app_user.id"], name=op.f("fk_document_template_updated_by")),
        schema="doc",
    )

    op.create_table(
        "document_render",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_template_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("document_no", sa.String(length=60), nullable=False),
        sa.Column("document_format", sa.String(length=10), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_name", sa.String(length=255), nullable=False),
        sa.Column("is_reprint", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_render_id", sa.Uuid(), nullable=True),
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("rendered_by", sa.Uuid(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "document_format IN ('PDF','XLSX')", name=op.f("ck_document_render_format")
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_document_render_size")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_render")),
        sa.UniqueConstraint("storage_name", name=op.f("uq_document_render_storage_name")),
        sa.ForeignKeyConstraint(
            ["document_template_id"],
            ["doc.document_template.id"],
            name=op.f("fk_document_render_document_template_id"),
        ),
        sa.ForeignKeyConstraint(
            ["source_render_id"], ["doc.document_render.id"], name=op.f("fk_document_render_source_render_id")
        ),
        sa.ForeignKeyConstraint(
            ["rendered_by"], ["seg.app_user.id"], name=op.f("fk_document_render_rendered_by")
        ),
        schema="doc",
    )
    op.create_index(
        op.f("ix_document_render_entity"),
        "document_render",
        ["entity_type", "entity_id", "rendered_at"],
        schema="doc",
    )

    op.create_table(
        "warehouse_voucher",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_no", sa.String(length=60), nullable=False),
        sa.Column("document_registry_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("mining_unit_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("source_requisition_id", sa.Uuid(), nullable=True),
        sa.Column("cost_center_code", sa.String(length=60), nullable=True),
        sa.Column("area", sa.String(length=120), nullable=True),
        sa.Column("usage_equipment", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("template_code", sa.String(length=40), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "status IN ('DRAFT','ISSUED')", name=op.f("ck_voucher_status_valido")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouse_voucher")),
        sa.UniqueConstraint("document_registry_id", name=op.f("uq_warehouse_voucher_registry")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_warehouse_voucher_idem")),
        sa.ForeignKeyConstraint(
            ["document_registry_id"], ["doc.document_registry.id"], name=op.f("fk_voucher_document_registry_id")
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["org.company.id"], name=op.f("fk_voucher_company_id")
        ),
        sa.ForeignKeyConstraint(
            ["mining_unit_id"], ["org.mining_unit.id"], name=op.f("fk_voucher_mining_unit_id")
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["org.department.id"], name=op.f("fk_voucher_department_id")
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["org.warehouse.id"], name=op.f("fk_voucher_warehouse_id")
        ),
        sa.ForeignKeyConstraint(
            ["source_requisition_id"], ["req.requisition.id"], name=op.f("fk_voucher_source_requisition_id")
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"], ["seg.app_user.id"], name=op.f("fk_voucher_issued_by")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["seg.app_user.id"], name=op.f("fk_voucher_created_by")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["seg.app_user.id"], name=op.f("fk_voucher_updated_by")
        ),
        schema="doc",
    )

    op.create_table(
        "warehouse_voucher_line",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("voucher_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("requisition_line_id", sa.Uuid(), nullable=True),
        sa.Column("stock_movement_id", sa.Uuid(), nullable=True),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column("item_code", sa.String(length=60), nullable=False),
        sa.Column("uom_code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("requested_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("dispatched_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("requested_qty >= 0", name=op.f("ck_voucher_line_requested_no_negativa")),
        sa.CheckConstraint("dispatched_qty >= 0", name=op.f("ck_voucher_line_dispatched_no_negativa")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouse_voucher_line")),
        sa.UniqueConstraint("voucher_id", "line_no", name=op.f("uq_voucher_line")),
        sa.ForeignKeyConstraint(
            ["voucher_id"], ["doc.warehouse_voucher.id"], name=op.f("fk_voucher_line_voucher_id")
        ),
        sa.ForeignKeyConstraint(
            ["requisition_line_id"],
            ["req.requisition_line.id"],
            name=op.f("fk_voucher_line_requisition_line_id"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_movement_id"], ["inv.stock_movement.id"], name=op.f("fk_voucher_line_stock_movement_id")
        ),
        sa.ForeignKeyConstraint(["item_id"], ["mdm.item.id"], name=op.f("fk_voucher_line_item_id")),
        sa.ForeignKeyConstraint(["created_by"], ["seg.app_user.id"], name=op.f("fk_voucher_line_created_by")),
        sa.ForeignKeyConstraint(["updated_by"], ["seg.app_user.id"], name=op.f("fk_voucher_line_updated_by")),
        schema="doc",
    )


def downgrade() -> None:
    raise RuntimeError("Las migraciones del módulo documental son aditivas; no se permite downgrade.")
