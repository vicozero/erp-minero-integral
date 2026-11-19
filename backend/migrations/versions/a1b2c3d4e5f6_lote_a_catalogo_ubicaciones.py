"""Lote A WMS — catálogos, ubicaciones, lotes, series y búsquedas.

Adiciones puras: no elimina columnas, no reescribe datos y no crea un segundo
inventario oficial. Las referencias ``lot_ref_id`` y ``location_ref_id`` son
nullable y conviven con los UUID centinela heredados.

Revision ID: a1b2c3d4e5f6
Revises: f4a7c1e2b3d6
Create Date: 2026-11-18
"""

from __future__ import annotations

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f4a7c1e2b3d6"
branch_labels = None
depends_on = None


AUDIT_COLUMNS = """
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES seg.app_user(id) ON DELETE RESTRICT,
    updated_at timestamptz,
    updated_by uuid REFERENCES seg.app_user(id) ON DELETE RESTRICT,
    version integer NOT NULL DEFAULT 1
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE mdm.item_family (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES org.company(id) ON DELETE RESTRICT,
            parent_id uuid REFERENCES mdm.item_family(id) ON DELETE RESTRICT,
            code text NOT NULL,
            name text NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            {AUDIT_COLUMNS},
            CONSTRAINT uq_item_family_company_code UNIQUE (company_id, code)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.item_uom_conversion (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id uuid NOT NULL REFERENCES mdm.item(id) ON DELETE RESTRICT,
            from_uom_id uuid NOT NULL REFERENCES mdm.uom(id) ON DELETE RESTRICT,
            to_uom_id uuid NOT NULL REFERENCES mdm.uom(id) ON DELETE RESTRICT,
            factor numeric(18,6) NOT NULL,
            is_base boolean NOT NULL DEFAULT false,
            is_purchase boolean NOT NULL DEFAULT false,
            is_issue boolean NOT NULL DEFAULT false,
            valid_from timestamptz NOT NULL DEFAULT now(),
            valid_to timestamptz,
            {AUDIT_COLUMNS},
            CONSTRAINT ck_item_uom_conversion_factor CHECK (factor > 0),
            CONSTRAINT uq_item_uom_conversion UNIQUE (item_id, from_uom_id, to_uom_id, valid_from)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.item_cross_reference (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id uuid NOT NULL REFERENCES mdm.item(id) ON DELETE RESTRICT,
            reference_type text NOT NULL,
            reference_code text NOT NULL,
            equivalent_item_id uuid REFERENCES mdm.item(id) ON DELETE RESTRICT,
            authorised boolean NOT NULL DEFAULT false,
            approved_by uuid REFERENCES seg.app_user(id) ON DELETE RESTRICT,
            valid_from timestamptz NOT NULL DEFAULT now(),
            valid_to timestamptz,
            source_hash text,
            notes text,
            {AUDIT_COLUMNS},
            CONSTRAINT ck_item_xref_type CHECK (
                reference_type IN ('INTERNAL','MANUFACTURER','CONTPAQI','GMAO','CUSTOMER')
            ),
            CONSTRAINT ck_item_xref_approval CHECK (authorised = false OR approved_by IS NOT NULL),
            CONSTRAINT uq_item_xref UNIQUE (item_id, reference_type, reference_code)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.item_supplier (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id uuid NOT NULL REFERENCES mdm.item(id) ON DELETE RESTRICT,
            supplier_id uuid NOT NULL REFERENCES mdm.supplier(id) ON DELETE RESTRICT,
            supplier_part_number text,
            lead_time_days integer NOT NULL DEFAULT 0,
            min_order_qty numeric(18,6) NOT NULL DEFAULT 0,
            preferred boolean NOT NULL DEFAULT false,
            last_unit_cost numeric(18,4),
            currency char(3) NOT NULL DEFAULT 'MXN',
            status text NOT NULL DEFAULT 'ACTIVE',
            {AUDIT_COLUMNS},
            CONSTRAINT ck_item_supplier_lead CHECK (lead_time_days >= 0),
            CONSTRAINT ck_item_supplier_moq CHECK (min_order_qty >= 0),
            CONSTRAINT ck_item_supplier_cost CHECK (last_unit_cost IS NULL OR last_unit_cost >= 0),
            CONSTRAINT ck_item_supplier_status CHECK (status IN ('ACTIVE','INACTIVE')),
            CONSTRAINT uq_item_supplier UNIQUE (item_id, supplier_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.storage_location (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            warehouse_id uuid NOT NULL REFERENCES org.warehouse(id) ON DELETE RESTRICT,
            parent_id uuid REFERENCES mdm.storage_location(id) ON DELETE RESTRICT,
            code text NOT NULL,
            zone text,
            aisle text,
            rack text,
            level text,
            position text,
            location_type text NOT NULL,
            qr_token text NOT NULL,
            capacity_qty numeric(18,6) NOT NULL DEFAULT 0,
            status text NOT NULL DEFAULT 'ACTIVE',
            is_pickable boolean NOT NULL DEFAULT true,
            is_receivable boolean NOT NULL DEFAULT true,
            {AUDIT_COLUMNS},
            CONSTRAINT ck_storage_location_type CHECK (
                location_type IN ('RECEIPT','STANDARD','QUARANTINE','DISPATCH','TRANSIT','SCRAP')
            ),
            CONSTRAINT ck_storage_location_status CHECK (status IN ('ACTIVE','BLOCKED','INACTIVE')),
            CONSTRAINT ck_storage_location_capacity CHECK (capacity_qty >= 0),
            CONSTRAINT uq_storage_location_code UNIQUE (warehouse_id, code),
            CONSTRAINT uq_storage_location_qr UNIQUE (qr_token)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.location_restriction (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            location_id uuid NOT NULL REFERENCES mdm.storage_location(id) ON DELETE RESTRICT,
            item_family_id uuid REFERENCES mdm.item_family(id) ON DELETE RESTRICT,
            item_id uuid REFERENCES mdm.item(id) ON DELETE RESTRICT,
            max_qty numeric(18,6),
            temperature_min numeric(7,2),
            temperature_max numeric(7,2),
            allows_lot_mix boolean NOT NULL DEFAULT true,
            allows_serial_mix boolean NOT NULL DEFAULT true,
            {AUDIT_COLUMNS},
            CONSTRAINT ck_location_restriction_target CHECK (
                item_family_id IS NOT NULL OR item_id IS NOT NULL
            ),
            CONSTRAINT ck_location_restriction_qty CHECK (max_qty IS NULL OR max_qty >= 0),
            CONSTRAINT uq_location_restriction UNIQUE (location_id, item_family_id, item_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.lot (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id uuid NOT NULL REFERENCES mdm.item(id) ON DELETE RESTRICT,
            lot_number text NOT NULL,
            manufactured_at timestamptz,
            expiry_date date,
            status text NOT NULL DEFAULT 'ACTIVE',
            external_id text,
            {AUDIT_COLUMNS},
            CONSTRAINT ck_lot_status CHECK (status IN ('ACTIVE','QUARANTINE','EXPIRED','BLOCKED')),
            CONSTRAINT uq_lot_item_number UNIQUE (item_id, lot_number)
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE mdm.serial (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id uuid NOT NULL REFERENCES mdm.item(id) ON DELETE RESTRICT,
            serial_number text NOT NULL,
            lot_id uuid REFERENCES mdm.lot(id) ON DELETE RESTRICT,
            status text NOT NULL DEFAULT 'ACTIVE',
            current_location_id uuid REFERENCES mdm.storage_location(id) ON DELETE RESTRICT,
            {AUDIT_COLUMNS},
            CONSTRAINT ck_serial_status CHECK (
                status IN ('ACTIVE','ISSUED','RETURNED','DAMAGED','LOST','RETIRED')
            ),
            CONSTRAINT uq_serial_item_number UNIQUE (item_id, serial_number)
        )
        """
    )

    op.execute(
        """
        ALTER TABLE mdm.item
            ADD COLUMN family_id uuid REFERENCES mdm.item_family(id) ON DELETE RESTRICT,
            ADD COLUMN manufacturer text,
            ADD COLUMN manufacturer_part_no text,
            ADD COLUMN barcode text,
            ADD COLUMN image_path text,
            ADD COLUMN image_sha256 text,
            ADD COLUMN weight_kg numeric(18,6),
            ADD COLUMN volume_m3 numeric(18,6),
            ADD COLUMN storage_temperature_min numeric(7,2),
            ADD COLUMN storage_temperature_max numeric(7,2),
            ADD COLUMN is_consumable boolean NOT NULL DEFAULT false,
            ADD COLUMN is_returnable boolean NOT NULL DEFAULT false,
            ADD COLUMN is_tool boolean NOT NULL DEFAULT false,
            ADD COLUMN default_supplier_id uuid REFERENCES mdm.supplier(id) ON DELETE RESTRICT,
            ADD COLUMN reorder_point numeric(18,6),
            ADD COLUMN safety_stock numeric(18,6),
            ADD COLUMN max_stock numeric(18,6)
        """
    )

    for table in ("stock_balance", "stock_reservation", "stock_movement"):
        op.execute(
            f"""
            ALTER TABLE inv.{table}
                ADD COLUMN lot_ref_id uuid REFERENCES mdm.lot(id) ON DELETE RESTRICT,
                ADD COLUMN location_ref_id uuid REFERENCES mdm.storage_location(id) ON DELETE RESTRICT
            """
        )

    op.execute("CREATE UNIQUE INDEX uq_item_barcode ON mdm.item(company_id, barcode) WHERE barcode IS NOT NULL")
    op.execute("CREATE INDEX ix_item_description ON mdm.item (lower(description))")
    op.execute("CREATE INDEX ix_item_xref_code ON mdm.item_cross_reference (reference_type, reference_code)")
    op.execute("CREATE INDEX ix_lot_expiry_date ON mdm.lot (expiry_date)")
    op.execute("CREATE INDEX ix_lot_item ON mdm.lot (item_id)")
    op.execute("CREATE INDEX ix_serial_item ON mdm.serial (item_id)")
    op.execute(
        "CREATE INDEX ix_storage_location_warehouse_type ON mdm.storage_location (warehouse_id, location_type)"
    )
    op.execute("CREATE INDEX ix_storage_location_zone ON mdm.storage_location (warehouse_id, zone)")
    op.execute("CREATE INDEX ix_stock_balance_location_ref ON inv.stock_balance (location_ref_id)")
    op.execute("CREATE INDEX ix_stock_balance_lot_ref ON inv.stock_balance (lot_ref_id)")

    op.execute(
        """
        CREATE VIEW mdm.v_item_search AS
        SELECT
            i.id,
            i.company_id,
            i.code,
            i.description,
            f.name AS family_name,
            i.family_id,
            i.manufacturer,
            i.manufacturer_part_no,
            i.barcode,
            i.uom_id,
            u.code AS uom_code,
            i.lot_tracked,
            i.serial_tracked,
            i.is_consumable,
            i.is_returnable,
            i.is_tool,
            i.is_active,
            i.standard_cost,
            i.default_supplier_id,
            s.name AS supplier_name
        FROM mdm.item i
        LEFT JOIN mdm.item_family f ON f.id = i.family_id
        LEFT JOIN mdm.uom u ON u.id = i.uom_id
        LEFT JOIN mdm.supplier s ON s.id = i.default_supplier_id
        """
    )

    op.execute(
        """
        CREATE VIEW mdm.v_location_occupancy AS
        SELECT
            l.id,
            l.warehouse_id,
            w.code AS warehouse_code,
            l.code AS location_code,
            l.location_type,
            l.status,
            l.capacity_qty,
            COALESCE(SUM(b.on_hand_qty), 0) AS occupied_qty,
            COUNT(DISTINCT b.item_id) AS item_count
        FROM mdm.storage_location l
        JOIN org.warehouse w ON w.id = l.warehouse_id
        LEFT JOIN inv.stock_balance b ON b.location_ref_id = l.id
        GROUP BY l.id, w.code
        """
    )

    op.execute(
        """
        CREATE VIEW inv.v_stock_by_location AS
        SELECT
            b.id,
            b.warehouse_id,
            b.item_id,
            i.code AS item_code,
            i.description AS item_description,
            b.lot_ref_id,
            lot.lot_number,
            b.location_ref_id,
            loc.code AS location_code,
            loc.zone,
            loc.aisle,
            b.on_hand_qty,
            b.reserved_qty,
            b.on_hand_qty - b.reserved_qty AS available_qty
        FROM inv.stock_balance b
        JOIN mdm.item i ON i.id = b.item_id
        LEFT JOIN mdm.lot lot ON lot.id = b.lot_ref_id
        LEFT JOIN mdm.storage_location loc ON loc.id = b.location_ref_id
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "La migración del Lote A no se revierte: contiene datos operativos. "
        "No ejecutar downgrade sobre bases reales o del piloto."
    )
