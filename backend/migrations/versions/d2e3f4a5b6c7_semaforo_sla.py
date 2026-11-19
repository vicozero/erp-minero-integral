"""Agrega políticas e historial del semáforo SLA de requisiciones.

La migración es aditiva: crea dos tablas nuevas en ``req`` y siembra cuatro
políticas globales propuestas por el asistente y aprobadas por el usuario.
El modo emergencia queda desactivado; no hay reversiones destructivas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

_POLICIES = (
    ("11111111-1111-4111-8111-000000000001", "LOW", 72, 96),
    ("11111111-1111-4111-8111-000000000002", "NORMAL", 48, 72),
    ("11111111-1111-4111-8111-000000000003", "HIGH", 24, 48),
    ("11111111-1111-4111-8111-000000000004", "URGENT", 8, 16),
)


def upgrade() -> None:
    op.create_table(
        "sla_policy",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("department_key", sa.String(length=36), nullable=False, server_default="ALL"),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("requisition_type", sa.String(length=20), nullable=False, server_default="ALL"),
        sa.Column("green_hours", sa.Integer(), nullable=False),
        sa.Column("yellow_hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("emergency_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("emergency_green_hours", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("emergency_yellow_hours", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("emergency_approved_by", sa.Uuid(), nullable=True),
        sa.Column("emergency_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.String(length=40), nullable=False, server_default="GLOBAL"),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "priority IN ('LOW','NORMAL','HIGH','URGENT')", name=op.f("ck_sla_policy_priority")
        ),
        sa.CheckConstraint(
            "requisition_type IN ('ALL','STOCK','PURCHASE','SERVICE')",
            name=op.f("ck_sla_policy_requisition_type"),
        ),
        sa.CheckConstraint("yellow_hours > green_hours", name=op.f("ck_sla_policy_horas")),
        sa.CheckConstraint(
            "emergency_yellow_hours > emergency_green_hours",
            name=op.f("ck_sla_policy_horas_emergencia"),
        ),
        sa.CheckConstraint(
            "NOT emergency_enabled OR "
            "(emergency_approved_by IS NOT NULL AND emergency_approved_at IS NOT NULL)",
            name=op.f("ck_sla_policy_emergencia_aprobada"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sla_policy")),
        sa.UniqueConstraint(
            "priority", "department_key", "requisition_type", name=op.f("uq_sla_policy_scope")
        ),
        sa.ForeignKeyConstraint(["department_id"], ["org.department.id"], name=op.f("fk_sla_policy_department_id")),
        sa.ForeignKeyConstraint(
            ["emergency_approved_by"], ["seg.app_user.id"], name=op.f("fk_sla_policy_emergency_approved_by")
        ),
        sa.ForeignKeyConstraint(["created_by"], ["seg.app_user.id"], name=op.f("fk_sla_policy_created_by")),
        sa.ForeignKeyConstraint(["updated_by"], ["seg.app_user.id"], name=op.f("fk_sla_policy_updated_by")),
        schema="req",
    )

    op.create_table(
        "requisition_sla_event",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("requisition_id", sa.Uuid(), nullable=False),
        sa.Column("base_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_hours", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("color", sa.String(length=10), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("policy_scope", sa.String(length=120), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "color IN ('GREEN','YELLOW','RED','NONE')", name=op.f("ck_sla_event_color")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requisition_sla_event")),
        sa.ForeignKeyConstraint(
            ["requisition_id"], ["req.requisition.id"], name=op.f("fk_sla_event_requisition_id")
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["req.sla_policy.id"], name=op.f("fk_sla_event_policy_id")),
        sa.ForeignKeyConstraint(["actor_id"], ["seg.app_user.id"], name=op.f("fk_sla_event_actor_id")),
        schema="req",
    )
    op.create_index(
        op.f("ix_requisition_sla_event_history"),
        "requisition_sla_event",
        ["requisition_id", "occurred_at"],
        schema="req",
    )
    op.create_index(
        op.f("ix_requisition_sla_event_color"),
        "requisition_sla_event",
        ["occurred_at", "color"],
        schema="req",
    )

    conn = op.get_bind()
    for policy_id, priority, green_hours, yellow_hours in _POLICIES:
        conn.execute(
            sa.text(
                """
                INSERT INTO req.sla_policy (
                    id, priority, department_key, department_id, requisition_type,
                    green_hours, yellow_hours, is_active, emergency_enabled,
                    emergency_green_hours, emergency_yellow_hours, scope, evidence, notes,
                    created_at, version
                ) VALUES (
                    CAST(:id AS uuid), :priority, 'ALL', NULL, 'ALL',
                    :green_hours, :yellow_hours, TRUE, FALSE,
                    4, 8, 'GLOBAL', :evidence, :notes, now(), 1
                )
                """
            ),
            {
                "id": policy_id,
                "priority": priority,
                "green_hours": green_hours,
                "yellow_hours": yellow_hours,
                "evidence": "Propuesta aprobada por el usuario el 19/11/2026.",
                "notes": "El modo emergencia requiere aprobación explícita y permiso sla.policy.approve.",
            },
        )


def downgrade() -> None:
    raise RuntimeError("Las migraciones de este proyecto son aditivas; no se permite downgrade.")
