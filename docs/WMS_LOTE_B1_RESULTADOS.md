# WMS Lote B.1 — Resultados

> Fecha: 2026-11-19
>
> Commit base verificado: `57c6fbb`
>
> Base utilizada: PostgreSQL real `erp_minero_test` (`127.0.0.1:5432`), usuario `erp_minero_app`
>
> Alembic final: `b7c8d9e0f1a3 (head)`
>
> Bandera `WMS_LOTE_B_ENABLED`: `False` (sin cambios)

---

## 1. Alcance ejecutado

Se preparó exclusivamente la estructura transaccional del Lote B.1. **No se activaron movimientos WMS**, no se creó el esquema físico `wms`, no se ejecutó backfill automático, no se hicieron movimientos de inventario reales y no se modificaron las reglas de reservas, entregas ni compras.

La decisión **D-06** continúa como `Pendiente` en `docs/ERP_MRO_WMS_DEPENDENCIAS.md`. No se encontró autorización documentada posterior para el esquema `wms`, por lo que se aplicó el **alcance reducido de la sección 4.1**: todos los objetos nuevos quedan en `inv` (más una vista de lectura en `req`).

No se tocó CONTPAQi ni Sierra Madre GMAO.

---

## 2. Migraciones aplicadas

| Revisión | Archivo | Propósito |
|---|---|---|
| `b7c8d9e0f1a2` | `backend/migrations/versions/b7c8d9e0f1a2_lote_b_movimientos_wms.py` | Estructura transaccional aditiva: detalle de existencias, columnas de movimiento, índices, restricciones, triggers, vistas y backfill manual. |
| `b7c8d9e0f1a3` | `backend/migrations/versions/b7c8d9e0f1a3_corrige_backfill_lote_b.py` | Corrección aditiva del backfill: PostgreSQL 17 no define `min(uuid)`; se reemplazó por `min(id::text)::uuid`. |

La revisión correctiva se detectó mediante prueba real: la primera ejecución de `inv.backfill_lote_b_detail()` falló con `UndefinedFunction: no existe la función min(uuid)`. No se editó ni se rebobinó la migración ya aplicada; se agregó una revisión posterior que reemplaza solo la función. El historial Alembic queda lineal y `downgrade()` sigue fallando deliberadamente porque B.1 es aditivo.

No se ejecutó `DROP`, `TRUNCATE` masivo sobre datos reales, `downgrade` ni backfill desde la migración.

---

## 3. Objetos SQL creados

### 3.1 Tabla y columnas

- `inv.stock_balance_detail`: proyección detallada por `stock_balance_id`, almacén, artículo, lote, serie, estado (`stock_state`) y ubicación. No reemplaza a `inv.stock_balance`; ambos son proyecciones del movimiento append-only.
- Columnas aditivas en `inv.stock_movement`: `stock_state`, `serial_id`, `occurred_at`, `scope_balance_after_qty`, `delivery_seq`, `return_seq`, `movement_group_id`, `return_of_movement_id`, `reversal_reason`, `reversal_requested_by`, `reversal_approved_by`, `approved_by`, `department_id`, `requester_id`, `equipment_id`, `cost_center_id`, `work_order_no` y `movement_order_line_id`.

`movement_order_line_id` queda sin llave foránea y con un `COMMENT` que documenta la referencia futura a `wms.movement_order_line.id` hasta que D-06 sea aprobada.

### 3.2 Índices y restricciones

- `uq_stock_balance_detail_scope`: índice único funcional con UUID centinela para `NULL`.
- Índices de detalle: `ix_sbd_warehouse_item_state`, `ix_sbd_lot_ref`, `ix_sbd_serial_id`, `ix_sbd_location_ref`.
- Índices únicos parciales: `uq_stock_movement_reversal_once`, `uq_movement_issue_seq`, `uq_movement_return_seq`.
- Índices de consulta: `ix_stock_movement_serial_id`, `ix_stock_movement_equipment_id`, `ix_stock_movement_cost_center_id`, `ix_stock_movement_work_order_no`, `ix_stock_movement_occurred_at`, `ix_stock_movement_movement_order_line_id`, `ix_stock_movement_return_of_id`.
- Llave primaria `pk_stock_balance_detail` y 8 llaves foráneas `fk_sbd_*` con `ON DELETE RESTRICT`.
- CHECKs de detalle: cantidades no negativas, reserva dentro de existencia, estado válido y reserva solo en `AVAILABLE`.
- CHECKs de movimiento: `stock_state` válido y secuencias `delivery_seq`/`return_seq` positivas.

### 3.3 Triggers y funciones

- `trg_stock_movement_no_update`, `trg_stock_movement_no_delete`, `trg_stock_movement_no_truncate`: inmutabilidad del hecho contable. El `TRUNCATE` solo se permite con `inv.allow_maintenance_truncate = 'on'`, bandera que se usa únicamente en el arnés de pruebas sobre `erp_minero_test`.
- `trg_stock_movement_reversal_guard`: exige `POSTED`, dirección opuesta, cantidad total e igualdad de ámbito (artículo, almacén, lote, serie, estado y ubicación); prohíbe reversos encadenados.
- `trg_stock_movement_return_guard`: exige un `ISSUE` de origen, dirección `IN`, secuencia positiva y que el total devuelto no exceda lo entregado.
- `trg_sbd_reconcile_balance` y `trg_sbd_reconcile_detail`: constraint triggers deferidos que comparan agregado contra detalle **solo cuando el ámbito ya tiene detalle**, para no imponer restricciones a registros heredados sin proyección.
- `inv.backfill_lote_b_detail()`: manual, idempotente, omite ámbitos con detalle previo, registra un evento en `aud.audit_log` y **no es invocada por Alembic**.

### 3.4 Vistas

- `inv.v_stock_balance_reconciliation`: estados `SIN_DETALLE`, `OK` y `DIVERGENTE`.
- `inv.v_kardex`: kardex con `signed_running_qty` por ámbito y documento de origen.
- `req.v_requisition_line_net_quantities`: cantidades derivadas para requisiciones, sin alterar tablas ni reglas del módulo.

---

## 4. Restricciones verificadas

| Escenario | Resultado |
|---|---|
| Migración aplicada y Alembic `head` | OK (`b7c8d9e0f1a3`) |
| Tablas, vistas, funciones y triggers presentes | OK |
| Índices, PK, FK y CHECKs correctos | OK |
| UPDATE de movimiento histórico | Rechazado por trigger |
| DELETE de movimiento histórico | Rechazado por trigger |
| Reversión duplicada | Rechazada por índice único parcial |
| Devolución inválida (excede entregado) | Rechazada por trigger |
| Divergencia agregado vs. detalle | Detectada con `SET CONSTRAINTS ALL IMMEDIATE` |
| Compatibilidad heredada sin detalle | OK; vista reporta `SIN_DETALLE` y el trigger no exige igualdad |
| Rollback ante error | OK; sin rastros de detalle insertado |
| Backfill manual e idempotente | OK; 3 filas en la primera llamada, 0 en la segunda, 2 eventos de auditoría |
| Concurrencia con conexiones independientes | OK; el segundo reverso esperó el bloqueo del original y terminó con SQLSTATE `55P03` (`lock_not_available`) |

No se usó SQLite para ninguna de estas validaciones.

---

## 5. Resultado de pruebas y regresión

| Verificación | Resultado |
|---|---|
| `python -m pytest -q tests/integration/test_migration_lote_b.py` | **11/11** |
| `python -m pytest -q` (backend completo) | **88/88** (77 base + 11 nuevas) |
| `python -m ruff check app tests migrations` | Sin hallazgos |
| `python -m mypy app` | Sin problemas en 66 archivos |
| `alembic current` en `erp_minero_test` | `b7c8d9e0f1a3 (head)` |
| `python scripts\verificar_portal.py` | **30/30** |
| Frontend test/build | No ejecutado: no hay cambios frontend en B.1 |

Se ajustaron tres arneses preexistentes para que la regresión reconociera B.1:

- `backend/tests/conftest.py`: bandera local de mantenimiento antes del `TRUNCATE` sintético.
- `backend/tests/test_phase4_requisiciones.py`: misma bandera en su reset propio, con verificación de base `erp_minero_test`.
- `backend/tests/test_postgres_phase2.py`: la lista de revisiones Alembic aceptadas incluye ahora `b7c8d9e0f1a2` y `b7c8d9e0f1a3`.

---

## 6. Incidencias del servicio PostgreSQL

Durante la primera aplicación de la migración se repitió la terminación anómala ya documentada en `docs/WMS_LOTE_B0_RESULTADOS.md`:

- `Application Error`, `postgres.exe 17.0.12`, código `0xc0000409`, módulo `ucrtbase.dll`.
- El servicio `postgresql-x64-17` pasó a `Stopped` y la conexión inicial expiró.
- Se reinició el servicio local. No se modificó configuración de red, puertos, `listen_addresses`, firewall ni archivos de PostgreSQL.
- Después del reinicio, la migración y todas las pruebas terminaron correctamente. El servicio quedó en `Running`.
- No se encontraron nuevas entradas `PANIC` ni `pg_control` en los logs tras el reinicio. Los logs históricos del 18/11 sí muestran `FATAL: no se pudo abrir el archivo «base/5/1249»` y apagados previos; se mantienen como incidencia de infraestructura sin resolver.

---

## 7. Decisiones pendientes

| Decisión | Estado | Impacto |
|---|---|---|
| D-01…D-05 | Pendientes | Requeridas para el flujo operativo completo del Lote B. |
| D-06 — esquema físico `wms` | Pendiente | B.1 usó solo `inv`; no se creó `wms` ni `wms.movement_order*`. |
| D-07 — política de aprobaciones | Pendiente | No se inventaron estados ni aprobaciones nuevas. |
| D-08…D-12 | Pendientes | No bloquean esta preparación estructural. |

No se asumió ninguna aprobación adicional.

---

## 8. Riesgos y bloqueo de concurrencia

La prueba concurrente confirma que dos conexiones independientes serializan sobre el movimiento original mediante `SELECT ... FOR UPDATE` en el guarda de reversos. Sin embargo, **esto no debe interpretarse como una solución de concurrencia completa**:

- Los triggers de reconciliación son `DEFERRABLE INITIALLY DEFERRED`. Detectan divergencia al confirmar la transacción (o con `SET CONSTRAINTS ALL IMMEDIATE`), pero no imponen por sí solos un orden determinístico de bloqueo entre escrituras concurrentes a `inv.stock_balance` e `inv.stock_balance_detail`.
- B.2 debe implementar el orden de bloqueo y la estrategia transaccional en el servicio (con reintento solo para deadlocks/serialización) antes de habilitar entradas, salidas o transferencias.
- La bandera `inv.allow_maintenance_truncate` es una excepción de mantenimiento para el arnés de pruebas; no debe usarse en código de aplicación.

Este bloqueo queda documentado en lugar de declarar que la restricción diferida garantiza consistencia bajo concurrencia.

---

## 9. Compatibilidad con sistemas existentes

- `inv.stock_balance` conserva sus columnas heredadas, incluidos los UUID centinela. No se eliminó ni renombró ninguna columna.
- El detalle nace vacío: la vista de conciliación reporta `SIN_DETALLE` para los saldos semilla y el trigger no los fuerza a tener proyección.
- CONTPAQi sigue siendo el inventario oficial; el detalle es una proyección operativa, no una segunda fuente oficial.
- No se escribió en GMAO ni en CONTPAQi; no se agregaron integraciones.
- No se crearon rutas `/api/v1/wms/movements`; el router WMS existente sigue siendo de catálogo y ubicaciones.
- `WMS_LOTE_B_ENABLED` permanece en `False`.

---

## 10. Próximo paso — B.2

B.2 debe implementar la capa transaccional de movimientos atómicos sobre estas estructuras, con:

1. Orden determinístico de bloqueo y manejo controlado de `deadlock`/`serialization_failure`.
2. Entradas y salidas que actualicen agregado y detalle en la misma transacción.
3. Uso real de `delivery_seq`, `return_seq`, `idempotency_key` y `movement_group_id` desde el servicio.
4. Reversión y devolución apoyadas en los guards creados aquí.
5. Pruebas de concurrencia que fallen si se elimina el orden de bloqueo.

B.1 queda preparado estructuralmente, pero **no se declara terminado operativamente**: la activación depende de B.2 y de las decisiones pendientes, en particular D-06.
