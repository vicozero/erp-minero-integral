# WMS Lote B — Matriz de riesgos y controles

> Estado: propuesta para revisión  
> Fecha: 2026-11-19  
> Referencias: `docs/WMS_LOTE_B_DISENO.md`, `docs/WMS_LOTE_B_PLAN.md`

---

## 1. Metodología

Riesgo = probabilidad × impacto. Escala: `B` bajo, `M` medio, `A` alto. Todo riesgo alto requiere control automático en base de datos o en servicio antes de activar el lote. La mitigación debe quedar verificada por prueba automatizada.

---

## 2. Matriz principal

| ID | Riesgo | Prob. | Impacto | Señal de alerta | Mitigación | Lote | Criterio de cierre |
|---|---|---|---|---|---|---|---|
| R01 | Doble salida por reintento con distinta clave | M | A | Dos `ISSUE` para la misma partida | `acquire()` + `delivery_seq` único + reserva bloqueada + `net_issued` | B.4 | C01/C02 pasan |
| R02 | Saldo agregado y detallado divergen | M | A | `v_stock_balance_reconciliation` con diferencia | Misma transacción + trigger deferido | B.1/B.3 | C12 pasa |
| R03 | Violación de única al crear saldo concurrente | A | M | `UniqueViolation` en pruebas | `INSERT ON CONFLICT DO NOTHING RETURNING` + `FOR UPDATE` | B.2 | C09 pasa |
| R04 | Deadlock entre scopes | M | M | `40P01` | Orden global de bloqueo; agregado antes que detalle | B.2 | C13 pasa |
| R05 | Reverso duplicado o encadenado | M | A | Dos `reversal_of_id` iguales | Índice parcial + trigger de reverso | B.1/B.6 | C04 pasa |
| R06 | Movimiento editado o borrado | B | A | `UPDATE`/`DELETE` directo | Trigger de inmutabilidad y no truncate | B.1 | C11 pasa |
| R07 | Sobre-recepción de OC | M | A | `received_qty > ordered_qty` | Bloqueo de OC/partidas + validación existente | B.3 | C05/C17 pasan |
| R08 | Devolución mayor a la entrega original | M | A | Suma de returns > ISSUE | `FOR UPDATE` sobre origen + trigger `return_limit` | B.5 | C15 pasa |
| R09 | Pick desde cuarentena o lote bloqueado | M | A | Movimiento con `stock_state <> AVAILABLE` | Filtro `AVAILABLE` + validación de estados | B.4/B.5 | C07/C08 pasan |
| R10 | Vencimiento de reserva concurrente con salida | A | M | Reserva `EXPIRED` con `consumed_qty > 0` | Mismo orden de bloqueo; expirar solo remanente | B.4 | C06 pasa |
| R11 | Serial duplicado recepcionado | M | A | Dos movimientos con el mismo `serial_id` | Bloqueo de `mdm.serial` + índice/estado | B.3 | C10 pasa |
| R12 | CostLayer duplicado por reintento de GRN | M | M | Dos capas por misma línea | Misma clave derivada por línea e idempotencia | B.3 | C17 pasa |
| R13 | Pérdida de contexto de negocio en kardex | M | M | Movimiento sin equipo/centro/OT | Snapshot inmutable en columnas nuevas | B.4 | Prueba de snapshot |
| R14 | Alcance RBAC insuficiente | M | A | Usuario ve kardex de otra unidad | `require_permission` + filtro de alcance | B.8 | C20 pasa |
| R15 | Backfill ejecutado sin autorización | B | A | Filas nuevas en base real sin ticket | Función manual, no llamada por migración | B.1/B.10 | Revisión de diff y logs |
| R16 | Cambio destructivo accidental | B | A | `DROP`/`TRUNCATE`/`downgrade` en diff | Revisión de diff + prohibiciones del plan | Todos | Cero coincidencias |
| R17 | Exposición de red | B | A | `--host 0.0.0.0` o puerto publicado | `127.0.0.1`, sin Docker publish | B.10 | Smoke local |
| R18 | Secretos o datos reales en Git | B | A | `.env`, dumps, exportaciones CONTPAQi | Revisión de `git diff` | Todos | Cero coincidencias |
| R19 | Reintento móvil con clave inestable | M | M | Movimientos duplicados por cantidad distinta | Clave derivada de documento + secuencia, no de cantidad | B.0/B.4 | Prueba de reintento |
| R20 | Cierre prematuro de requisición | M | M | Requisición `CLOSED` con partida pendiente | Bloqueo de partidas + `net_issued` | B.4 | C18 pasa |
| R21 | Falta de auditoría en reverso/cuarentena | M | A | Movimiento sin `AuditEntry` | `AuditService.record` en mismo tx | B.8 | Revisión de bitácora |
| R22 | Migración fallida a media aplicación | B | M | Alembic parcial | DDL en transacción; reintento tras corrección | B.1 | `empty->head` en sintética |

---

## 3. Riesgos críticos detallados

### R01 — Doble salida

**Escenario:** dos peticiones con la misma intención física pero distinta representación de cantidad o distinta clave client-side.  
**Control:** clave canónica por documento/partida/secuencia, `delivery_seq` único, bloqueo de partida y reserva, `net_issued`.  
**Fallback:** feature flag desactiva el endpoint nuevo sin afectar `/inventory/issues`.

### R02 — Divergencia de proyecciones

**Escenario:** se actualiza detalle pero no agregado, o viceversa.  
**Control:** un único método de repositorio escribe ambas proyecciones; trigger diferido rechaza el `COMMIT`.  
**Fallback:** reporte `v_stock_balance_reconciliation` y ajuste autorizado; nunca borrar filas.

### R04 — Deadlock

**Escenario:** una operación bloquea detalle A y otra detalle B en orden inverso.  
**Control:** rank global documentado en el diseño; helper `lock_scope_rows()` ordena y centraliza.  
**Fallback:** reintento solo en `40P01`/`40001`, con backoff acotado; nunca reintentar errores de regla de negocio.

### R05/R06 — Reversos e inmutabilidad

**Escenario:** corrección editando el movimiento original o generando dos reversos.  
**Control:** trigger de inmutabilidad + índice parcial + validación de reverso completo.  
**Fallback:** si se detecta un reverso inválido ya confirmado, se revierte el reverso; el original queda intacto.

### R08/R09 — Devoluciones y cuarentena

**Escenario:** devolución excesiva o surtido desde stock retenido.  
**Control:** bloqueo del movimiento original, trigger de límite, estados no reservables, aprobación para liberación.  
**Fallback:** reversar la devolución o el par de ajuste, nunca eliminar.

### R14/R18 — Seguridad y secretos

**Escenario:** bypass de permisos o filtrado de credenciales en logs/diff.  
**Control:** `require_permission`, alcance por unidad/almacén, revisión de diff, sin secretos en repo.  
**Fallback:** desactivar endpoints, rotar credenciales fuera del repo si se expusieron, documentar incidente.

---

## 4. Controles compensatorios y kill-switch

| Control | Activación | Efecto |
|---|---|---|
| `WMS_LOTE_B_ENABLED=false` | Bug en endpoints nuevos | Desactiva routers B sin afectar inventario heredado |
| Triggers de inmutabilidad | Cualquier intento de edición | Falla la transacción, queda evidencia en logs |
| Trigger de reconciliación | Divergencia de proyecciones | Falla el `COMMIT` |
| Índices parciales | Reverso/entrega/devolución duplicada | Falla la inserción |
| `AuditService.record` | Toda acción sensible | Registro inmutable con actor y `request_id` |
| Vista de reconciliación | Reporte diario | Detecta diferencias antes de cerrar turno |
| Feature flag por endpoint | Incidentes parciales | Permite desactivar solo entradas, salidas o reversos |

---

## 5. Plan de respuesta a incidentes

1. **Detener:** desactivar el endpoint o el flag correspondiente.
2. **Aislar:** identificar `warehouse_id`, `item_id`, lote/serie y rango de fechas desde kardex.
3. **No borrar:** nunca `UPDATE`, `DELETE` ni `TRUNCATE` sobre movimientos.
4. **Compensar:** crear `REVERSAL` o par de ajuste con motivo y aprobación.
5. **Reconciliar:** ejecutar `inv.v_stock_balance_reconciliation` hasta diferencia cero.
6. **Documentar:** registrar hallazgo, causa, corrective action y prueba nueva que evite repetición.
7. **Reactivar:** solo después de que la prueba de regresión pase.

---

## 6. Riesgos aceptados temporalmente

| Riesgo | Aceptación | Compensación |
|---|---|---|
| Saldos heredados sin detalle hasta backfill | Migración no toca datos reales | Vista reporta `legacy_without_detail`; backfill manual con ticket |
| Reversos parciales no soportados | Lote B usa reverso completo | Diferencias parciales se derivan al Lote D |
| `work_order_no` sin FK | No existe entidad OT en el código actual | Texto indexado y snapshot en movimiento |
| Costos solo en recepción de compra | Lote F implementará valuación completa | `CostLayer` heredado se conserva sin duplicar |

---

## 7. Criterios de cierre del plan de riesgos

- R01–R14 tienen prueba automatizada verde.
- No hay riesgos `A` sin control automático.
- `git diff` sin patrones destructivos ni secretos.
- Bitácora y kardex explican el mismo conjunto de movimientos.
- Queda documentado el siguiente paso: Lote C (traspasos y material en tránsito).
