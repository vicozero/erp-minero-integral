# WMS avanzado — Modelo de datos propuesto

**Fecha:** 2026-11-18

**Estado:** DISEÑO. No se ejecutaron migraciones nuevas.

**Base actual:** head `f4a7c1e2b3d6`; 41 tablas de dominio + `public.alembic_version`.
**Regla:** toda migración será aditiva, con `downgrade` bloqueado sobre datos reales.

---

## 1. Convenciones heredadas

| Concepto | Regla |
|---|---|
| Identificador | `UUID`, `gen_random_uuid()` |
| Cantidad | `NUMERIC(18,6)`, nunca `float` |
| Importe | `NUMERIC(18,4)` por precisión fiscal; presentación en MXN |
| Porcentaje | `NUMERIC(7,4)` entre 0 y 100 |
| Fecha | `TIMESTAMPTZ`, presentación `America/Mexico_City` |
| Auditoría | `created_at/by`, `updated_at/by` en entidades mutables |
| Hechos | `stock_movement`, `cost_posting`, `audit_log`, `document_event`, `outbox_event`: inmutables |
| Borrado | Prohibido. Se usan `is_active`, `status` o `valid_to` |
| Documento | `document_registry_id` + `document_no` único vía `next_document_number()` |
| Idempotencia | `idempotency_key` único y registro en `doc.idempotency_record` |
| FK | `ondelete='RESTRICT'` |
| Nombres | `ck_`, `uq_`, `ix_`, `fk_` con prefijo de tabla; evitar doble prefijo detectado en Fase 4 |

---

## 2. Tablas actuales reutilizables

| Tabla actual | Uso WMS | Extensión requerida |
|---|---|---|
| `mdm.item` | Catálogo base | Atributos de familia, fabricante, foto, pesos, consumible/retornable/herramienta |
| `mdm.uom` | Unidades | Conversiones por artículo |
| `mdm.supplier` | Proveedores | Relación artículo-proveedor, lead time, MOQ, precio referencial |
| `org.warehouse` | Almacén | No se duplica; se usa como raíz de ubicaciones |
| `inv.stock_balance` | Saldo operativo | Referencias reales a lote/ubicación sin eliminar columnas legacy |
| `inv.stock_movement` | Ledger | Referencias a orden/tarea, lote, ubicación, serie y costo |
| `inv.stock_reservation` | Reservas | Referencia opcional a OT y ubicación/lote |
| `pur.goods_receipt(_line)` | Entradas de OC | Lote, serie, inspección y evidencia |
| `cost.cost_layer` | Capas | Asientos y consumo de capas por movimiento |
| `doc.*` | Numeración/idempotencia | Sin cambios estructurales |
| `intg.*` | Integración | Mapeo, batch, staging y conciliación |
| `aud.audit_log` | Bitácora | Sin cambios; trigger de inmutabilidad vigente |

### 2.1 Columnas legacy de lote y ubicación

Hoy `inv.stock_balance.lot_id`, `stock_reservation.lot_id`, `stock_movement.lot_id` y sus homólogos `location_id` son UUID con centinela `NULL_UUID` y **sin FK**.

Estrategia aditiva:

1. Crear `mdm.lot` y `mdm.storage_location`.
2. Añadir columnas nuevas nullable `lot_ref_id` y `location_ref_id` con FK real.
3. Mantener las columnas antiguas durante la transición.
4. Agregar CHECK de coherencia: si `lot_ref_id` es nulo, el valor legacy debe ser `NULL_UUID`, y viceversa.
5. Las nuevas operaciones escriben ambas columnas; las consultas nuevas usan `*_ref_id`.
6. No se eliminan columnas ni se reescriben filas antiguas sin ticket.

---

## 3. Lote A — Catálogos, ubicaciones y búsquedas

### 3.1 `mdm.item_family`

| Columna | Tipo | Regla |
|---|---|---|
| `id` | UUID PK | — |
| `company_id` | UUID FK `org.company` | `RESTRICT` |
| `parent_id` | UUID FK a sí misma | Jerarquía; `RESTRICT` |
| `code` | TEXT | Único por `(company_id, code)` |
| `name` | TEXT | Obligatorio |
| `is_active` | BOOLEAN | Default `true` |

### 3.2 Extensión de `mdm.item`

Columnas **nullable** para no romper datos actuales:

- `family_id` → `mdm.item_family`
- `manufacturer` TEXT
- `manufacturer_part_no` TEXT
- `barcode` TEXT, único por compañía cuando no nulo
- `image_path` TEXT (ruta controlada fuera de BD)
- `image_sha256` TEXT
- `weight_kg NUMERIC(18,6) >= 0`
- `volume_m3 NUMERIC(18,6) >= 0`
- `storage_temperature_min/max NUMERIC(7,2)` opcional
- `is_consumable`, `is_returnable`, `is_tool` BOOLEAN
- `default_supplier_id` → `mdm.supplier`
- `reorder_point`, `safety_stock`, `max_stock NUMERIC(18,6)` (preparación para Lote I; no operativos aún)

### 3.3 `mdm.item_uom_conversion`

| Columna | Regla |
|---|---|
| `item_id`, `from_uom_id`, `to_uom_id` | FK `RESTRICT` |
| `factor NUMERIC(18,6)` | `> 0` |
| `is_base`, `is_purchase`, `is_issue` | BOOLEAN, al menos uno verdadero |
| `valid_from`, `valid_to` | Rangos controlados |
| UNIQUE | `(item_id, from_uom_id, to_uom_id, valid_from)` |

### 3.4 `mdm.item_cross_reference`

Para equivalencias autorizadas, no sustituciones silenciosas.

- `item_id` (artículo original)
- `reference_code` (código externo o interno alterno)
- `reference_type` ∈ `INTERNAL`, `MANUFACTURER`, `CONTPAQI`, `GMAO`, `CUSTOMER`
- `equivalent_item_id` nullable → `mdm.item`
- `authorised BOOLEAN` default `false`
- `approved_by` → `seg.app_user`, obligatorio si `authorised=true`
- `valid_from`, `valid_to`
- `source_hash` para detección de duplicados
- CHECK: si `authorised=true` entonces `approved_by IS NOT NULL`
- UNIQUE: `(company_id, reference_type, reference_code)`

### 3.5 `mdm.item_supplier`

- `item_id`, `supplier_id`
- `supplier_part_number`
- `lead_time_days >= 0`
- `min_order_qty > 0`
- `preferred BOOLEAN`
- `last_unit_cost NUMERIC(18,4) >= 0`
- `currency CHAR(3)` default `MXN`
- `status`
- PK `(item_id, supplier_id)`
- Al menos un proveedor preferido por artículo: validación en servicio, no constraint global.

### 3.6 `mdm.storage_location`

| Columna | Regla |
|---|---|
| `warehouse_id` | FK `org.warehouse`, `RESTRICT` |
| `parent_id` | FK a sí misma para jerarquía |
| `code` | Único por `(warehouse_id, code)` |
| `zone`, `aisle`, `rack`, `level`, `position` | TEXT opcionales |
| `location_type` | `RECEIPT`, `STANDARD`, `QUARANTINE`, `DISPATCH`, `TRANSIT`, `SCRAP` |
| `qr_token` | TEXT único, generado localmente; never una credencial |
| `capacity_qty NUMERIC(18,6)` | `>= 0` |
| `status` | `ACTIVE`, `BLOCKED`, `INACTIVE` |
| `is_pickable`, `is_receivable` | BOOLEAN |

Índices: `(warehouse_id, location_type)`, `(warehouse_id, zone)`, `qr_token`, búsqueda por jerarquía.

### 3.7 `mdm.location_restriction`

- `location_id` → `mdm.storage_location`
- `item_family_id` → `mdm.item_family`, nullable
- `item_id` → `mdm.item`, nullable
- `max_qty NUMERIC(18,6) >= 0`
- `temperature_min/max`
- `allows_lot_mix`, `allows_serial_mix` BOOLEAN
- CHECK: al menos uno de `item_family_id` o `item_id`
- UNIQUE por combinación aplicable.

### 3.8 `mdm.lot`

- `item_id` FK
- `lot_number` TEXT
- `manufactured_at`, `expiry_date`
- `status` ∈ `ACTIVE`, `QUARANTINE`, `EXPIRED`, `BLOCKED`
- `external_id` nullable
- UNIQUE `(item_id, lot_number)`
- Índice por `expiry_date` para FEFO.

### 3.9 `mdm.serial`

- `item_id` FK
- `serial_number` TEXT
- `lot_id` nullable → `mdm.lot`
- `status` ∈ `ACTIVE`, `ISSUED`, `RETURNED`, `DAMAGED`, `LOST`, `RETIRED`
- `current_location_id` nullable → `mdm.storage_location`
- UNIQUE `(item_id, serial_number)`

### 3.10 Vistas de búsqueda del Lote A

- `mdm.v_item_search`: código, descripción, familia, fabricante, UOM, flags, proveedor preferido, disponibilidad agregada por almacén.
- `mdm.v_location_occupancy`: ubicación, capacidad, saldo ocupado, artículos distintos, estado.
- `inv.v_stock_by_location`: saldo por almacén/artículo/lote/ubicación con `available_qty`.

Ninguna vista escribe datos.

---

## 4. Lote B — Entradas, salidas, devoluciones y kardex

### 4.1 `wms.movement_order` / `wms.movement_order_line`

Cabecera:

- `order_no` desde `next_document_number`
- `order_type` ∈ `RECEIPT`, `ISSUE`, `RETURN`, `ADJUSTMENT`
- `source_document_type/id`
- `warehouse_id`, `location_id`
- `status` ∈ `DRAFT`, `APPROVED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`
- `requested_by`, `approved_by`, `executed_by`, `received_by`
- `document_registry_id`

Línea:

- `line_no`, `item_id`, `lot_ref_id`, `serial_id`, `location_ref_id`
- `quantity`, `uom_id`
- `status`, `picked_qty`, `confirmed_qty`
- `idempotency_key`

### 4.2 `wms.movement_task`

- `order_line_id`, `task_type` ∈ `PICK`, `PUTAWAY`, `COUNT`, `LOAD`, `UNLOAD`
- `assigned_to`, `status`, `started_at`, `completed_at`
- `source_location_id`, `target_location_id`
- `evidence_sha256`, `evidence_path`
- `idempotency_key`

### 4.3 Extensiones de `inv.stock_movement`

Añadir nullable:

- `movement_order_line_id`
- `lot_ref_id`, `location_ref_id`, `serial_id`
- `transfer_id` (preparación Lote C)
- `cost_posting_id` (preparación Lote F)
- `external_system_id`, `external_document_id`
- `occurred_at`

### 4.4 `inv.stock_adjustment(_line)`

- Cabecera con motivo, autorizador, documento y estado.
- Línea con `counted_qty`, `system_qty`, `difference_qty`, `movement_id`.
- Siempre genera `ADJUSTMENT_IN/OUT`; nunca actualiza un movimiento anterior.

### 4.5 Kardex valorizado

`inv.v_kardex_valorizado`: movimiento, fecha, documento, artículo, almacén, ubicación, lote, serie, cantidad, dirección, saldo, costo unitario, costo total, actor y objeto de costo.

---

## 5. Lote C — Traspasos y material en tránsito

### 5.1 `inv.transfer` / `inv.transfer_line`

- `transfer_no` documentado
- `source_warehouse_id`, `target_warehouse_id`
- `source_unit_id`, `target_unit_id`
- `status` ∈ `REQUESTED`, `APPROVED`, `PREPARING`, `IN_TRANSIT`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CANCELLED`
- Solicitud, autorización, preparación y recepción con actores separados.
- Línea con cantidades solicitada, preparada, despachada, recibida y diferencias.

### 5.2 `inv.transfer_shipment` / `inv.transfer_receipt`

- Guía/manifiesto, fecha, operario, evidencia.
- Recepciones parciales con idempotencia.
- Diferencias conciliadas con motivo y autorización.

### 5.3 `inv.in_transit_balance`

Proyección separada, nunca sumada a `available_qty`:

- `transfer_id`, `item_id`, `lot_ref_id`, `quantity`, `from/to warehouse`.
- Se elimina lógicamente al recibir; no se resta de `on_hand` del almacén destino hasta la recepción.

---

## 6. Lote D — Inventarios físicos

| Tabla | Propósito |
|---|---|
| `wms.count_plan` | Plan general/cíclico/ABC/por zona/ciego, periodicidad y alcance |
| `wms.count_session` | Ejecución por almacén/zona, fecha, bloqueo de movimientos, contadores |
| `wms.count_line` | Artículo/ubicación/lote, cantidad sistema, cantidad contada, reconteo |
| `wms.count_difference` | Diferencia, motivo, clasificación y autorización |
| `inv.inventory_snapshot` | Foto operativa por almacén/artículo/lote/ubicación/costo |
| `inv.inventory_reconciliation(_line)` | Comparación y resolución de diferencias |

Reglas de BD:

- `counted_qty >= 0`.
- `difference_qty = counted_qty - system_qty`.
- Una sesión `BLOCKING` impide movimientos en el alcance mediante validación de servicio + bandera consultable.
- El ajuste sólo se genera tras autorización.

---

## 7. Lote E — Herramientas

| Tabla | Propósito |
|---|---|
| `mnt.tool` | Extensión de equipo para herramienta retornable, calibración y estado físico |
| `mnt.tool_loan` | Préstamo individual o por cuadrilla, responsable, fecha, OT |
| `mnt.tool_loan_line` | Herramienta, cantidad, devolución parcial, estado |
| `mnt.tool_inspection` | Inspección, daño, extravío y evidencia |
| `mnt.tool_calibration` | Frecuencia, última calibración, vencimiento |

El préstamo no descuenta `inv.stock_balance` salvo que la herramienta esté modelada como artículo de inventario; esta decisión queda pendiente (AD-05).

---

## 8. Lote F — Costos

| Tabla | Regla |
|---|---|
| `cost.cost_policy` | Método autorizado por compañía/artículo, vigencia y aprobación |
| `cost.cost_object` | Tipos `WORK_ORDER`, `EQUIPMENT`, `MINING_LOCATION`, `DEPARTMENT`, `PROJECT`, `SHIFT` |
| `cost.cost_posting` | Inmutable; movimiento origen, cuenta, monto, objeto de costo, estado |
| `cost.cost_allocation` | Porcentajes por asiento; suma 100 |
| `inv.stock_movement_cost` | Relación movimiento ↔ capa de costo, cantidad consumida y unit_cost |
| `cost.inventory_aging_view` | Días de inventario, obsoleto e inmovilizado |

Prohibido inventar métodos contables. Sólo se activa el método aprobado por Finanzas.

---

## 9. Lote G — Captura móvil, QR y mapa visual

| Tabla | Propósito |
|---|---|
| `wms.mobile_device` | Dispositivo autorizado, usuario, almacén permitido, estado |
| `wms.scan_event` | Código leído, resultado, idempotencia, timestamp, Device ID |
| `wms.label_template` | Plantilla de etiqueta; nunca datos reales en plantillas de prueba |
| `wms.label_print_job` | Solicitud de impresión, estado y evidencia |
| `wms.location_map` | Versión del plano 2D por almacén, JSONB de zonas/ubicaciones |

La evidencia fotográfica usa la misma estrategia que `req.requisition_attachment`: archivo fuera de BD + SHA-256 + metadatos.

---

## 10. Lote H — Reabastecimiento, analítica e IA

| Tabla | Propósito |
|---|---|
| `wms.reorder_rule` | Min/máx, punto de reorden, stock de seguridad, lead time, criticidad |
| `wms.replenishment_suggestion` | Sugerencia con cantidad, motivo, validez y estado de aprobación |
| `wms.demand_forecast` | Serie temporal sintética/autorizada, horizonte, confianza, versión |
| `wms.anomaly_alert` | Anomalía detectada, severidad, evidencia y disposición humana |
| `wms.recommendation` | Tipo, entrada, salida, confianza, explicación, aprobador |
| `wms.duplicate_candidate` | Artículos candidatos a duplicado con puntaje y revisión |
| `wms.kpi_snapshot` | Métricas calculadas por periodo para dashboard |

Regla crítica: una sugerencia aprobada genera un documento normal; nunca escribe directamente `stock_movement`.

---

## 11. Integración CONTPAQi

Tablas propuestas en `intg`:

- `external_mapping`: sistema, tipo de entidad, ID interno, clave externa, hash, estado.
- `integration_batch`: archivo, nombre, SHA-256, tamaño, usuario, filas, resultado.
- `integration_staging`: lote, número de fila, payload JSONB, validación y error.
- `external_document_ref`: documento interno, tipo externo, folio externo, estado.
- `reconciliation_snapshot(_line)`: foto operativa vs oficial y diferencia.

Ver `docs/WMS_MATRIZ_INTEGRACION_CONTPAQI.md`.

---

## 12. Estrategia de migraciones

1. Una migración por lote, con ID explícito y `downgrade` bloqueado.
2. Primero crear maestros (`mdm`), luego columnas nullable en tablas existentes, después FKs y vistas.
3. No eliminar `NULL_UUID` ni columnas legacy en la misma migración.
4. Sembrar datos sintéticos nuevos de forma idempotente.
5. Probar `alembic upgrade head` desde base vacía en cada lote.
6. Verificar que no aparezcan constraints duplicados por el naming convention.
7. No usar `DROP`, `TRUNCATE`, `DELETE` masivo ni `downgrade` sobre piloto/datos reales.

---

## 13. Criterios de aceptación del modelo

- 41 tablas actuales siguen intactas; las nuevas son aditivas.
- Un saldo por `(almacén, artículo, lote_ref, ubicación_ref)` sin duplicados.
- Toda tabla de hechos tiene idempotencia y auditoría.
- Toda FK usa `RESTRICT`.
- Ninguna tabla nueva almacena `on_hand_qty` como verdad oficial.
- Las vistas derivadas son consultables y no escriben.
- Los datos de prueba son sintéticos y reconocibles con `@example.invalid`.
- La migración del Lote A pasa de `empty` a `head` y conserva la semilla actual.
