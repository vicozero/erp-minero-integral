# WMS Lote B — Diseño seguro de entradas, salidas, devoluciones y kardex

> Estado: propuesta para revisión e implementación  
> Fecha: 2026-11-19  
> Línea base: commit local `bcf27bd`  
> Alcance: diseño únicamente. No se aplicaron migraciones, no se escribió en BD, no se ejecutó push ni integración externa.

---

## 0. Resumen ejecutivo

El Lote A dejó un catálogo WMS enriquecido (`mdm.storage_location`, `mdm.lot`, `mdm.serial`, `lot_ref_id`, `location_ref_id`) sin cambiar los saldos heredados. El Lote B debe convertir ese catálogo en movimientos físicos auditables sin romper `inv.stock_balance`, `inv.stock_reservation` ni los contratos actuales de `/api/v1/inventory/*`.

La decisión central es **no repurposear** las columnas heredadas `lot_id` y `location_id` de `inv.stock_balance`. Se mantienen como UUID centinela `00000000-0000-0000-0000-000000000000` y se introduce una proyección detallada `inv.stock_balance_detail` que desagrega el mismo hecho por artículo, almacén, lote, serie, estado y ubicación. La fuente de verdad sigue siendo el movimiento append-only; el saldo agregado y el saldo detallado son proyecciones materializadas en la misma transacción y se reconcilian con restricciones diferidas.

Resultado esperado: entradas, salidas, devoluciones, cuarentena, reversos y kardex con idempotencia atómica, bloqueos deterministas y cero dobles salidas.

---

## 1. Estado actual inspectado

| Elemento | Situación confirmada | Implicación para Lote B |
|---|---|---|
| `inv.stock_balance` | Única `(warehouse_id, item_id, lot_id, location_id)`; `lot_id`/`location_id` NOT NULL con centinela; `on_hand_qty >= reserved_qty >= 0`. | No alterar `uq_stock_scope`. La granularidad real va en una tabla nueva. |
| `inv.stock_reservation` | `quantity`, `consumed_qty`, estados `ACTIVE/CONSUMED/RELEASED/EXPIRED`, `idempotency_key` única, refs Lote A nullable. | `issue()` debe seguir consumiendo reservas FIFO; la versión enriquecida debe actualizar también el detalle. |
| `inv.stock_movement` | Append-only por convención, con `reversal_of_id`, `idempotency_key` única, `status='POSTED'`, `balance_after_qty`, refs Lote A nullable. | Falta inmutabilidad DB, unicidad parcial de reverso y campos de contexto. Se agregan de forma aditiva. |
| `InventoryService._get_or_create_balance()` | `SELECT ... FOR UPDATE` sobre centinela; si no existe, `INSERT`. | Riesgo de violación de única concurrente. Sustituir por `INSERT ... ON CONFLICT DO NOTHING RETURNING` + `SELECT FOR UPDATE`. |
| `InventoryService.reserve()` | Bloquea partida, valida autorizado, descuenta disponible del saldo centinela. | Compatible; se extiende sin cambiar claves ni contratos. |
| `InventoryService.issue()` | Exige reserva activa, consume FIFO, valida `delivered + qty <= authorised_qty`, descuenta `on_hand` y `reserved`, cierra requisición. | Base correcta; faltan lote/serie/ubicación/estado, reversos y neteo. |
| `InventoryService.receive_stock()` | Crea `RECEIPT/IN`, suma `on_hand`, escribe `balance_after_qty` centinela. | Debe aceptar opcionalmente lote/serie/ubicación/estado y sincronizar detalle. |
| `PurchasingService.receive()` | Bloquea OC y partidas, valida sobre-recepción, llama `receive_stock` con clave `{grn_key}:{line.id}`, crea `CostLayer`. | No duplicar CostLayer; reutilizar la misma clave por línea. |
| Idempotencia | `acquire()` usa `INSERT ... ON CONFLICT DO NOTHING RETURNING`; nunca SELECT previo. | Mantener tal cual. No reemplazar por patrón SELECT-then-INSERT. |
| Numeración | `next_document_number()` bloquea secuencia por tipo/empresa/unidad/serie/año y registra evento de documento. | Todo movimiento nuevo debe tener `movement_no` y `document_registry_id`. |
| Lote A | `Lot.status ∈ ACTIVE/QUARANTINE/EXPIRED/BLOCKED`; `Serial.status ∈ ACTIVE/ISSUED/RETURNED/DAMAGED/LOST/RETIRED`; ubicaciones con `is_pickable`, `is_receivable`, `location_type`, restricciones. | Provee las reglas de elegibilidad para picking y putaway. |
| Requisición | Ya trae `company_id`, `mining_unit_id`, `department_id`, `warehouse_id`, `equipment_id`, `cost_center_id`, `requester_id`, `work_order_no`. | Copiar como snapshot inmutable al movimiento. No existe entidad OT con FK; `work_order_no` sigue siendo texto. |

---

## 2. Modelo de existencias por artículo, almacén, lote, serie, estado y ubicación

### 2.1 Principio de una sola verdad

- **Hecho canónico:** `inv.stock_movement` (append-only).
- **Proyección de compatibilidad:** `inv.stock_balance` (centinela), usada por los endpoints actuales.
- **Proyección WMS:** `inv.stock_balance_detail`, desagregada por dimensión física.
- Ambas proyecciones se actualizan **en la misma transacción**. Un trigger de restracción diferida verifica que `SUM(detalle) = saldo agregado` al confirmar.

Esto evita crear un segundo inventario oficial: no hay dos saldos independientes, sino dos vistas materializadas del mismo conjunto de movimientos.

### 2.2 Tabla `inv.stock_balance_detail`

Columnas aditivas:

```text
id                 uuid PK
stock_balance_id   uuid NOT NULL FK inv.stock_balance.id RESTRICT
warehouse_id       uuid NOT NULL FK org.warehouse.id
item_id            uuid NOT NULL FK mdm.item.id
lot_ref_id         uuid NULL FK mdm.lot.id
serial_id          uuid NULL FK mdm.serial.id
stock_state        text NOT NULL
location_ref_id    uuid NULL FK mdm.storage_location.id
on_hand_qty        numeric(18,6) NOT NULL DEFAULT 0
reserved_qty       numeric(18,6) NOT NULL DEFAULT 0
auditoría          created_at/created_by/updated_at/updated_by/version
```

Índice único funcional:

```sql
CREATE UNIQUE INDEX uq_stock_balance_detail_scope
ON inv.stock_balance_detail (
    warehouse_id,
    item_id,
    COALESCE(lot_ref_id,    '00000000-0000-0000-0000-000000000000'::uuid),
    COALESCE(serial_id,     '00000000-0000-0000-0000-000000000000'::uuid),
    stock_state,
    COALESCE(location_ref_id, '00000000-0000-0000-0000-000000000000'::uuid)
);
```

Restricciones:

```text
on_hand_qty >= 0
reserved_qty >= 0
on_hand_qty >= reserved_qty
stock_state IN ('AVAILABLE','QUARANTINE','INSPECTION','BLOCKED','DAMAGED','IN_TRANSIT','SCRAP')
stock_state <> 'AVAILABLE' => reserved_qty = 0
```

`available_qty` **no se almacena**: se deriva como `on_hand_qty - reserved_qty`.

### 2.3 Estados de stock y su correspondencia

| `stock_state` | Significado | Origen típico | Pickable | Reservable |
|---|---|---|---|---|
| `AVAILABLE` | Existencia libre y conforme | Recepción a ubicación `RECEIPT/STANDARD`, liberación de cuarentena | Sí | Sí |
| `INSPECTION` | Devuelto o recibido pendiente de revisión | Devolución, recepción dudosa | No | No |
| `QUARANTINE` | Retenido por calidad o incidente | Cambio de estado desde `AVAILABLE`/`INSPECTION` | No | No |
| `BLOCKED` | Lote, serie o ubicación bloqueada | `Lot.status=BLOCKED`, `Serial.status=LOST/RETIRED`, ubicación `BLOCKED` | No | No |
| `DAMAGED` | Daño confirmado | Reporte de daño | No | No |
| `IN_TRANSIT` | Preparación para Lote C | Reserva de transferencia | No | No |
| `SCRAP` | Destino final de desecho | Ubicación `SCRAP` | No | No |

Reglas de mapeo:

- `Lot.status=ACTIVE` ⇒ estado de stock `AVAILABLE` si la ubicación permite recepción/picking.
- `Lot.status=QUARANTINE` ⇒ `QUARANTINE`; `BLOCKED`/`EXPIRED` ⇒ `BLOCKED`.
- `Serial.status=ACTIVE` ⇒ `AVAILABLE`; `RETURNED` ⇒ `INSPECTION`; `DAMAGED/LOST/RETIRED` ⇒ `DAMAGED/BLOCKED/SCRAP`.
- `Serial.status=ISSUED` no genera fila de existencia; el serial queda fuera de stock hasta una devolución.

### 2.4 Reglas por tipo de artículo

- `Item.lot_tracked=true`: exige `lot_ref_id` en entradas y salidas; se prohíbe mezclar lotes si `LocationRestriction.allows_lot_mix=false`.
- `Item.serial_tracked=true`: exige exactamente un `serial_id` por unidad de salida; cada serial debe estar `ACTIVE` y no duplicado.
- `Item.is_returnable=false`: rechaza devoluciones de consumo; permite solo devolución por falla de calidad con aprobación.
- `Item.is_tool=true`: ruta futura Lote E; en Lote B solo se registra consumo, sin préstamo.
- `Item.is_consumable=true`: no requiere serie; puede omitir lote si `lot_tracked=false`.

### 2.5 Conciliación

Vista `inv.v_stock_balance_reconciliation`:

```text
scope (warehouse_id, item_id)
legacy_on_hand_qty   = COALESCE(inv.stock_balance.on_hand_qty, 0)
detail_on_hand_qty   = COALESCE(SUM(inv.stock_balance_detail.on_hand_qty), 0)
legacy_reserved_qty  = COALESCE(inv.stock_balance.reserved_qty, 0)
detail_reserved_qty  = COALESCE(SUM(inv.stock_balance_detail.reserved_qty), 0)
diferencia_on_hand   = legacy - detail
diferencia_reserved  = legacy - detail
```

Trigger diferido `trg_sbd_reconcile` sobre ambas tablas eleva excepción si alguna diferencia es distinta de cero al hacer `COMMIT`.

---

## 3. Reglas de entradas y salidas transaccionales

### 3.1 Orden común de ejecución

Toda operación Lote B sigue este orden estricto:

1. Validar esquema Pydantic y permiso RBAC.
2. `acquire()` de idempotencia con clave canónica.
3. Bloquear cabecera y partidas del documento fuente por UUID ascendente.
4. Bloquear maestros involucrados: `mdm.serial`, `mdm.lot`, `mdm.storage_location`, en ese orden y por UUID ascendente.
5. Bloquear `inv.stock_balance` agregado por `(warehouse_id, item_id)` ascendente.
6. Bloquear filas `inv.stock_balance_detail` ordenadas por `(warehouse_id, item_id, lot_key, serial_key, stock_state, location_key, id)`.
7. Validar reglas de negocio.
8. Mutar proyecciones, insertar movimiento, auditoría, eventos y document registry.
9. `complete()` de idempotencia.
10. `COMMIT` atómico en el router.

### 3.2 Entradas

Fuentes permitidas en Lote B: `GOODS_RECEIPT`, `RETURN`, `ADJUSTMENT_IN` controlado, `INITIAL` solo en semilla sintética.

Validaciones previas:

- Documento fuente existe, está en estado permitido y sus partidas están bloqueadas.
- `location.is_receivable=true`, `location.status='ACTIVE'` y `location.location_type ∈ ('RECEIPT','STANDARD','QUARANTINE','INSPECTION')`.
- `capacity_qty` y `LocationRestriction.max_qty` no se exceden.
- Lote no `BLOCKED`/`EXPIRED`; si `expiry_date < CURRENT_DATE`, requiere aprobación explícita o destino `QUARANTINE`.
- Serial no duplicado y con estado admitido para la entrada.
- Cantidad `> 0` y `NUMERIC(18,6)`; nunca `float`.
- Costo solo se crea en recepciones de compra (`CostLayer` con la misma clave por línea).

Efectos en la misma transacción:

```text
stock_balance.on_hand_qty          += qty
stock_balance_detail.on_hand_qty   += qty   (destino por lote/serie/estado/ubicación)
stock_movement                     INSERT RECEIPT/IN o RETURN/IN
serial.current_location_id         = ubicación destino (si aplica)
serial.status                      = ACTIVE o RETURNED -> INSPECTION
audit + emit + document_event      INSERT
idempotency_record                 COMPLETED
```

`balance_after_qty` conserva su significado heredado (saldo agregado). El saldo del ámbito detallado se escribe en la columna nueva `scope_balance_after_qty`.

### 3.3 Salidas

Fuentes permitidas: requisición autorizada, orden de movimiento `ISSUE`, OT referida por `work_order_no`.

Validaciones previas:

- Partida de requisición bloqueada; requisición en `APPROVED` o `PARTIALLY_APPROVED`.
- Existe reserva `ACTIVE` no vencida que cubra la cantidad; se consumen en orden `created_at, id`.
- `location.is_pickable=true`, `location.status='ACTIVE'`.
- `stock_state='AVAILABLE'` en la fila detallada seleccionada.
- Lote/serie elegibles según la sección 2.3.
- `net_issued + qty <= authorised_qty`, donde `net_issued = SUM(ISSUE) - SUM(REVERSAL de ISSUE)`.
- `delivery_seq` único por partida para evitar dos entregas con distinta clave pero mismo evento físico.

Efectos:

```text
reservation.consumed_qty           += parte consumida
reservation.status                 = CONSUMED cuando consumed_qty = quantity
stock_balance.on_hand_qty          -= qty
stock_balance.reserved_qty         -= qty
stock_balance_detail.on_hand_qty   -= qty
stock_balance_detail.reserved_qty  -= qty
serial.status                      = ISSUED
stock_movement                     INSERT ISSUE/OUT
audit + emit + document_event      INSERT
idempotency_record                 COMPLETED
```

Si todas las partidas están conciliadas, se mantiene el cierre actual de requisición, usando la cantidad neta para la comparación.

### 3.4 Política de selección

- Por defecto `FEFO` si el lote tiene `expiry_date`; si no, `FIFO` por `created_at`.
- La selección se hace sobre filas `AVAILABLE`, ordenadas por `expiry_date NULLS LAST, created_at, id`, con `FOR UPDATE`.
- La política se registra en la bitácora para que el kardex explique por qué se eligió ese lote/serie.

---

## 4. Devoluciones y cuarentena

### 4.1 Devolución

Una devolución es un movimiento `RETURN/IN` que referencia al movimiento `ISSUE/OUT` original mediante `return_of_movement_id`.

Reglas:

- Solo se devuelve contra un `ISSUE` POSTED, mismo artículo y almacén.
- `return_seq` incremental por movimiento original; `SUM(return.quantity) <= original.quantity`.
- La validación se hace con `SELECT ... FOR UPDATE` sobre el movimiento original y se refuerza con trigger `trg_stock_movement_return_guard`.
- El destino por defecto es `stock_state='INSPECTION'` en ubicación `QUARANTINE`, aunque el artículo sea `is_returnable=true`; la liberación a `AVAILABLE` requiere aprobación.
- La devolución **no revierte** la entrega: el consumo sigue en el kardex; la devolución es una entrada nueva con su propio documento.
- `Serial.status` pasa de `ISSUED` a `RETURNED`.

### 4.2 Cuarentena

La cuarentena no es una edición de movimiento. Es un par de movimientos enlazados por `movement_group_id`:

```text
ADJUSTMENT_OUT desde AVAILABLE  ->  ADJUSTMENT_IN hacia QUARANTINE
```

Reglas:

- Ambas patas en la misma transacción y con la misma `movement_group_id`.
- Se prohíbe reservar o surtir desde `QUARANTINE`, `INSPECTION`, `BLOCKED`, `DAMAGED`, `SCRAP`.
- La liberación invierte el par: `ADJUSTMENT_OUT` desde `QUARANTINE` → `ADJUSTMENT_IN` hacia `AVAILABLE`, con `approved_by` obligatorio.
- Nunca se actualiza `stock_state` directamente sin movimiento; el trigger de inmutabilidad y el trigger de reconciliación protegen el hecho.
- `Lot.status=QUARANTINE` o `location.location_type='QUARANTINE'` son señales de elegibilidad, no sustituto del movimiento.

---

## 5. Kardex con movimientos inmutables y reversos

### 5.1 Inmutabilidad

`inv.stock_movement` pasa a ser append-only también en base de datos:

- Trigger `BEFORE UPDATE OR DELETE`: lanza excepción.
- Trigger `BEFORE TRUNCATE`: lanza excepción.
- No se permite cambiar `status`, `quantity`, `balance_after_qty` ni referencias.
- Las correcciones son **reversos** o pares de ajuste, nunca `UPDATE`.

### 5.2 Reversos

Columnas aditivas ya existentes y nuevas:

```text
reversal_of_id          existente, FK self RESTRICT
reversal_reason         nuevo
reversal_requested_by   nuevo FK seg.app_user.id
reversal_approved_by    nuevo FK seg.app_user.id
```

Reglas:

- El reverso es un movimiento nuevo con `movement_type='REVERSAL'` y dirección opuesta al original.
- Cantidad igual a la original; se prohíben reversos parciales en Lote B (las diferencias parciales van a ajustes del Lote D).
- No se admiten reversos encadenados: si `original.reversal_of_id IS NOT NULL`, se rechaza.
- Mismo artículo, almacén, lote, serie y ubicación que el original.
- Índice parcial `uq_stock_movement_reversal_once ON (reversal_of_id) WHERE reversal_of_id IS NOT NULL` garantiza un solo reverso.
- Trigger `trg_stock_movement_reversal_guard` valida dirección, cantidad, dimensión y ausencia de reverso previo.
- El reverso revierte las proyecciones: suma/resta en `stock_balance` y `stock_balance_detail`, y actualiza `NetIssued` cuando el original fue un `ISSUE`.

### 5.3 Vista `inv.v_kardex`

Proyección de lectura sobre `inv.stock_movement`, sin tabla duplicada:

```text
movement_no, posted_at, occurred_at, movement_type, direction, quantity
item_id/item_code, warehouse_id/warehouse_code
location_ref_id/location_code/zone, lot_ref_id/lot_number, serial_id/serial_number
stock_state, balance_after_qty, scope_balance_after_qty
signed_running_qty  = SUM(CASE direction WHEN 'IN' THEN quantity ELSE -quantity END)
                      OVER (PARTITION BY item_id, warehouse_id, lot_key, serial_key, location_key
                            ORDER BY occurred_at, posted_at, id ROWS UNBOUNDED PRECEDING)
source_document_type/id, document_no
requisition_line_id, equipment_id, cost_center_id, work_order_no, requester_id
created_by, reversal_of_id, return_of_movement_id, movement_group_id
unit_cost, total_cost desde cost.cost_layer por source_document
```

Filtros soportados: `item_id`, `warehouse_id`, `location_ref_id`, `lot_ref_id`, `serial_id`, rango de fechas, `movement_type`, `document_no`, `equipment_id`, `cost_center_id`, `work_order_no`, `actor`.

---

## 6. Bloqueos PostgreSQL y orden consistente de adquisición

Aislamiento por defecto: `READ COMMITTED`. `SERIALIZABLE` solo para operaciones multiagregado autorizadas, con reintento controlado en `40001`/`40P01`.

Orden global de bloqueo (rank ascendente, UUID ascendente dentro de cada rank):

```text
1. doc.idempotency_record       -> acquire() con INSERT ... ON CONFLICT DO NOTHING RETURNING
2. documento fuente             -> cabecera, luego partidas
3. movimiento original          -> solo en returns/reversals (SELECT ... FOR UPDATE)
4. maestros mdm                 -> serial, lot, storage_location
5. inv.stock_balance            -> por (warehouse_id, item_id)
6. inv.stock_balance_detail     -> por scope completo
7. cost.cost_layer              -> solo si se valúa en la misma transacción
```

Reglas operativas:

- Nunca bloquear detalle antes que agregado; el agregado es la puerta de entrada y evita ciclos con el código heredado.
- Para dos scopings (preparación de Lote C), ordenar por `(warehouse_id, item_id, lot_key, serial_key, stock_state, location_key)` antes de bloquear.
- Creación segura de agregado y detalle:

```sql
INSERT INTO inv.stock_balance (...) VALUES (...) ON CONFLICT DO NOTHING RETURNING id;
-- si no hay fila: SELECT ... FOR UPDATE
INSERT INTO inv.stock_balance_detail (...) VALUES (...) ON CONFLICT DO NOTHING RETURNING id;
-- si no hay fila: SELECT ... FOR UPDATE
```

- No usar `SELECT` previo para decidir inserción: es la misma debilidad ya evitada en `idempotency.acquire()`.
- Configurar `SET LOCAL lock_timeout` y `SET LOCAL statement_timeout` por transacción WMS para fallar rápido en lugar de acumular esperas.
- Las lecturas de kardex no bloquean; usan `SELECT` plano.

---

## 7. Idempotencia atómica y prevención de doble salida

### 7.1 Clave canónica

Formato recomendado, alineado con `WMS_ARQUITECTURA.md`:

```text
SHA256(company_id | source_type | source_id | line_id | operation | sequence)
```

Reglas:

- La clave se calcula del documento fuente y su secuencia, **no de la cantidad**, para que un reintento con distinta representación decimal no cree otro movimiento.
- Los endpoints heredados conservan sus claves actuales (`reserve:...`, `issue:...`, `{grn_key}:{line.id}`).
- Los nuevos endpoints usan `movement_order_line.idempotency_key` como clave canónica.
- Longitud 3–160 caracteres; si la clave pertenece a otra operación, `409`.
- `acquire()` se ejecuta antes de cualquier efecto y `complete()` después de insertar el movimiento, dentro de la misma transacción.

### 7.2 Doble salida

Barreras en cascada:

1. `acquire()` serializa reintentos con la misma clave.
2. `RequisitionLine` se bloquea con `FOR UPDATE`.
3. Las reservas activas se bloquean y se consumen FIFO.
4. `delivery_seq` único por partida mediante índice parcial.
5. `net_issued + qty <= authorised_qty` se evalúa con el movimiento original y sus reversos.
6. `stock_balance_detail.reserved_qty >= qty` y `stock_state='AVAILABLE'` se validan bajo bloqueo.
7. `balance_after_qty >= 0` permanece como CHECK de la base.

Si dos peticiones distintas intentan surtir la misma reserva, una consume y la otra falla con `409` sin escribir movimiento ni auditoría incompleta.

---

## 8. Relaciones con requisiciones, equipos, OT y centros de costo

El movimiento conserva referencias y additionally guarda un **snapshot inmutable** del contexto para que el kardex no cambie si después se edita la requisición.

| Dato | Origen | Columna en `inv.stock_movement` |
|---|---|---|
| Requisición / partida | `req.requisition_line.id` | `requisition_line_id` (existente) |
| Empresa / unidad minera | `req.requisition.*` | vía `document_registry`/numbering; no se duplica |
| Departamento | `req.requisition.department_id` | `department_id` nuevo, nullable FK |
| Solicitante | `req.requisition.requester_id` | `requester_id` nuevo, nullable FK |
| Equipo | `req.requisition.equipment_id` | `equipment_id` nuevo, nullable FK `mnt.equipment` |
| Centro de costo | `req.requisition.cost_center_id` | `cost_center_id` nuevo, nullable FK `cost.cost_center` |
| Orden de trabajo | `req.requisition.work_order_no` | `work_order_no` nuevo, texto |
| Orden WMS | `wms.movement_order_line.id` | `movement_order_line_id` nuevo, nullable FK |
| Actor que ejecuta | `AppUser.id` | `created_by` existente |

Reglas:

- Para `ISSUE` desde requisición, `cost_center_id` es obligatorio en servicio aunque la columna sea nullable para soportar recepciones.
- Si existe `equipment_id`, centro de costo se toma de la requisición; si no, se usa el `cost_center_id` del equipo como fallback validado.
- No existe entidad OT con FK en el código actual; `work_order_no` se conserva como texto y se indexa. No se inventa `mnt.work_order`.
- `source_document_type` amplía su semántica con `MOVEMENT_ORDER`, `RETURN_ORDER`, `WORK_ORDER` (texto), sin cambiar el tipo de columna.

---

## 9. Compatibilidad con saldos y reservas actuales

Garantías:

- `uq_stock_scope`, `lot_id`, `location_id` y `NULL_UUID` quedan intactos.
- `/api/v1/inventory/availability|reservations|issues|kardex|reservations/expire` mantienen request/response.
- `InventoryService.line_reserved_qty()` y `line_delivered_qty()` conservan su significado heredado.
- Se agregan helpers nuevos, no se modifican los existentes:
  - `line_net_issued_qty()` = ISSUES − REVERSAL de ISSUES.
  - `line_detailed_reserved_qty()` = reservas con `lot_ref_id`/`location_ref_id`.
- `receive_stock()` recibe parámetros opcionales nuevos con defaults `None`; las llamadas actuales de compras no cambian.
- `_release_reservation()` debe descontar `reserved_qty` del detalle cuando la reserva tenga refs enriquecidas; si no, solo del agregado, como hoy.
- `expire_reservations()` mantiene su contrato y añade el ajuste detallado.
- Las claves de idempotencia actuales no se renombran; las nuevas usan otro prefijo.
- Migraciones sin `DROP`, `TRUNCATE`, `DELETE` masivo ni `downgrade`.
- Feature flag `WMS_LOTE_B_ENABLED=false` permite activar progresivamente los nuevos endpoints sin tocar los antiguos.

Backfill:

- La migración es **solo esquema**.
- Se proporciona `SELECT inv.backfill_lote_b_detail()` idempotente, manual y auditado, que crea una fila `AVAILABLE` por saldo agregado no cero con refs en centinela.
- No se ejecuta automáticamente sobre datos reales; en el piloto sintético se ejecuta con autorización del ticket.

---

## 10. Migraciones aditivas y plan de recuperación

### 10.1 Migración `b7c8d9e0f1a2_lote_b_movimientos_wms.py`

`down_revision = a1b2c3d4e5f6`. Contenido:

1. `CREATE TABLE inv.stock_balance_detail` con índices y CHECKs de la sección 2.
2. Nuevas tablas `wms.movement_order`, `wms.movement_order_line`, `wms.movement_task`.
3. `ALTER TABLE inv.stock_movement ADD COLUMN ...` todos los campos de las secciones 4, 5 y 8.
4. Índices parciales:
   - `uq_stock_movement_reversal_once`
   - `uq_movement_issue_seq`
   - `uq_movement_return_seq`
   - índices simples de `movement_order_line_id`, `serial_id`, `equipment_id`, `cost_center_id`, `work_order_no`, `occurred_at`.
5. Funciones y triggers:
   - `fn_block_movement_mutation` + triggers de UPDATE/DELETE/TRUNCATE.
   - `fn_check_reversal` + trigger BEFORE INSERT.
   - `fn_check_return_limit` + trigger BEFORE INSERT.
   - `fn_check_sbd_reconcile` + constraint triggers deferidos en ambas tablas de saldo.
6. Vistas:
   - `inv.v_stock_balance_reconciliation`
   - `inv.v_kardex`
   - `req.v_requisition_line_net_quantities`
7. Función manual `inv.backfill_lote_b_detail()`.
8. `downgrade()` lanza `RuntimeError`; no reversión automática.

### 10.2 Verificación de migración

- `alembic upgrade head` sobre base **sintética** desde `empty`.
- Inspección de columnas, índices, triggers y vistas.
- Prueba de que un `UPDATE` a `inv.stock_movement` falla.
- Prueba de que un reverso duplicado falla por índice.
- Prueba de que un `COMMIT` con diferencia de reconciliación falla.

### 10.3 Recuperación

| Situación | Acción |
|---|---|
| Migración fallida a mitad | Alembic envuelve DDL en transacción; corregir y reintentar. No crear tablas a mano en producción. |
| Endpoint nuevo con bug | `WMS_LOTE_B_ENABLED=false`; los endpoints heredados siguen operando. |
| Movimiento incorrecto ya confirmado | Crear `REVERSAL` con motivo y aprobación; nunca borrar ni editar el original. |
| Devolución excesiva detectada | Trigger la bloquea antes del commit; si ya se aplicó, reversar la devolución. |
| Divergencia agregado/detalle | Trigger diferido impide el commit; si aparece en datos heredados, ejecutar backfill controlado o ajuste autorizado del Lote D. |
| Deadlock `40P01` | Revisar orden de bloqueo; reintentar solo transacciones serializables/deadlock, nunca reglas de negocio. |
| Necesidad de revertir esquema | No ejecutar `downgrade`. Dejar tablas aditivas y desactivar código. |

---

## 11. Matriz de pruebas de concurrencia e integridad

Todas con PostgreSQL real y datos sintéticos. `SQLite` no es válido para esta matriz.

| ID | Escenario | Concurrencia / preparación | Resultado esperado | Aserción clave |
|---|---|---|---|---|
| C01 | Doble salida, misma clave | 2 hilos, mismo `idempotency_key` | 1 movimiento; ambas respuestas devuelven el mismo `id` | `COUNT(ISSUE)=1`, estado idempotencia `COMPLETED` |
| C02 | Doble salida, distinta clave, misma reserva | 2 hilos, claves distintas, reserva única | 1 éxito, 1 `409` | `consumed_qty <= quantity`, `net_issued <= authorised_qty` |
| C03 | Reserva concurrente | 2 reservas sobre la misma partida | Suma reservada ≤ autorizado y ≤ disponible | `on_hand >= reserved`, sin sobre-reserva |
| C04 | Reverso duplicado | 2 reversos del mismo movimiento | 1 éxito, 1 fallo de índice/trigger | `COUNT(reversal_of_id=X)=1` |
| C05 | Recepción concurrente OC | 2 GRN sobre la misma partida pendiente | No sobre-recepción | `received_qty <= ordered_qty - cancelled_qty` |
| C06 | Expiración vs salida | `expire_reservations` e `issue` simultáneos | Gana uno; nunca se consume una reserva `EXPIRED` | `reserved_qty >= 0`, statuses coherentes |
| C07 | Cuarentena vs picking | Putaway a `QUARANTINE` mientras otro intenta surtir | Pick no ve qty en cuarentena | Solo se consumen filas `AVAILABLE` |
| C08 | Bloqueo de lote/serie/ubicación | Cambio de status concurrente con issue | Después del commit del bloqueo, issue se rechaza | Sin movimientos desde `BLOCKED` |
| C09 | Creación concurrente de saldo | 2 primeras recepciones del mismo scope | 1 fila agregada, 1 detalle, cantidades sumadas | Sin `UniqueViolation` |
| C10 | Serial duplicado | 2 recepciones con el mismo serial | 1 éxito, 1 `409` | `Serial.status` único y coherente |
| C11 | Inmutabilidad | `UPDATE`/`DELETE`/`TRUNCATE` directo | Error de base | Trigger lanza excepción |
| C12 | Reconciliación | Modificar detalle sin agregado | `COMMIT` falla | Trigger deferido detecta diferencia |
| C13 | Orden de bloqueo | Dos operaciones sobre scopes A/B en orden inverso | Sin `40P01` | Orden canónico aplicado |
| C14 | Idempotencia entre operaciones | Misma clave para `reserve` e `issue` | `409` | `acquire()` rechaza operación distinta |
| C15 | Devolución excesiva | Dos devoluciones parciales que suman > original | Segunda rechazada | Trigger `return_limit` |
| C16 | Devolución inválida | Devolver contra `RECEIPT` o artículo distinto | Rechazo | Trigger valida tipo y dimensión |
| C17 | CostLayer duplicado | Reintento de GRN con misma clave | 1 capa por movimiento | `COUNT(cost_layer por movement)=1` |
| C18 | Cierre de requisición | Issue concurrente con cierre | No se cierra antes de conciliar | Partidas bloqueadas, estado final correcto |
| C19 | Reverso de ISSUE | Reversar entrega y volver a intentar entregar | Cantidad neta liberada correctamente | `net_issued` descontado |
| C20 | Alcance RBAC | Usuario de otra unidad minera consulta kardex ajeno | `403` o filtro vacío según política | `require_permission` + scope |

Ejecución sugerida:

```text
pytest -q backend/tests/inventory/test_lote_b_concurrency.py
pytest -q backend/tests/inventory/test_lote_b_integrity.py
pytest -q backend/tests/purchasing/test_lote_b_receipts.py
```

---

## 12. Criterios de aceptación y decisiones pendientes

### Criterios de aceptación

- Saldos agregado y detallado reconcilian al confirmar.
- No existe segunda salida con la misma intención física.
- Todo movimiento nuevo tiene documento, idempotencia, auditoría y evento.
- Reversos y devoluciones referencian su origen y no se editan hechos.
- Kardex consultable por lote, serie, ubicación, equipo, centro de costo y OT.
- Migración probada de `empty` a `head` en base sintética.
- Pruebas heredadas siguen pasando.

### Decisiones pendientes

1. Confirmar si las devoluciones deben descontar `line_delivered_qty` (en el diseño no: solo los reversos lo hacen).
2. Definir autorizador formal para liberación de cuarentena.
3. Definir si `expiry_date` vencida bloquea o solo advierte.
4. Decidir cuándo ejecutar `inv.backfill_lote_b_detail()` en el piloto.
5. Confirmar política FEFO vs FIFO por familia de artículo.
