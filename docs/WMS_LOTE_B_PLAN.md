# WMS Lote B — Plan de implementación por lotes pequeños

> Estado: plan propuesto  
> Fecha: 2026-11-19  
> Línea base: commit local `bcf27bd`  
> Documento de referencia: `docs/WMS_LOTE_B_DISENO.md`

---

## 1. Reglas de ejecución

1. Trabajar solo en `E:\ERP_MINERO`.
2. Leer `AGENTS.md` y `docs/WMS_LOTE_B_DISENO.md` antes de tocar código.
3. No sobrescribir cambios del usuario; verificar `git status` antes de empezar cada lote.
4. No modificar CONTPAQi, GMAO ni sus datos.
5. No ejecutar `DROP`, `TRUNCATE`, `DELETE` masivo, `alembic downgrade`, push ni despliegue.
6. Servidor local solo en `127.0.0.1`.
7. Datos sintéticos únicamente.
8. Cada lote termina con pruebas automatizadas ejecutadas localmente.
9. Un commit local por lote, mensaje en español e imperativo.
10. Si una regla de negocio no está clara, preguntar antes de asumir.

---

## 2. Secuencia de lotes

| Lote | Nombre | Entregable principal | Depende de |
|---|---|---|---|
| B.0 | Contratos y bandera | Permisos, alias, esquemas Pydantic y feature flag | — |
| B.1 | Migración aditiva | `b7c8d9e0f1a2_lote_b_movimientos_wms.py` | B.0 |
| B.2 | Modelos y repositorio | `StockBalanceDetail`, órdenes WMS, helpers de bloqueo | B.1 |
| B.3 | Entradas | Recepción enriquecida y endpoint de entradas | B.2 |
| B.4 | Salidas | Salida enriquecida con doble barrera anti duplicado | B.3 |
| B.5 | Devoluciones y cuarentena | Devolución con límite y pares de estado | B.4 |
| B.6 | Reversos e inmutabilidad | Servicio/API de reversos; triggers ya en B.1 | B.5 |
| B.7 | Kardex y reconciliación | Endpoints de kardex, saldos y reporte de diferencias | B.6 |
| B.8 | Auditoría, permisos y alcance | Cableado RBAC, bitácora y filtro por unidad/almacén | B.7 |
| B.9 | Frontend mínimo | Pantallas de entradas, salidas, devoluciones y kardex | B.8 |
| B.10 | Verificación final | Pruebas, build, portal smoke, documentación y commit | B.9 |

---

## 3. Detalle por lote

### B.0 — Contratos y bandera

**Archivos**
- `backend/app/shared/constants.py`
- `backend/app/core/config.py`
- `backend/app/modules/inventory/wms_movement_schemas.py` (nuevo)

**Cambios**
- Permisos canónicos: `wms.receipt.create`, `wms.receipt.approve`, `wms.issue.create`, `wms.issue.approve`, `wms.return.create`, `wms.return.approve`, `wms.reversal.create`, `wms.reversal.approve`, `wms.kardex.view`, `warehouse.stock.view`.
- Aliases en español: `almacenes.entradas`, `almacenes.salidas`, `almacenes.devoluciones`, `almacenes.reversos`, `entradas.crear`, `salidas.crear`, `devoluciones.crear`, `reversos.crear`. Conservar `almacenes.kardex -> inventory.kardex.view`.
- Roles: `ALMACENISTA`/`ALMACEN` reciben creación y consulta; `APROBADOR` recibe aprobación; `GERENCIA`/`AUDITOR` solo consulta; `ADMIN` todos.
- `WMS_LOTE_B_ENABLED: bool = False`.
- Esquemas Pydantic para `ReceiptIn`, `IssueInWms`, `ReturnIn`, `ReversalIn`, `MovementOrderOut`, `KardexEntryOut`.

**Pruebas**
- Validación de esquemas y aliases.
- Import de la app sin endpoints nuevos activos.

**Terminado cuando**
- `pytest -q backend/tests/unit/test_lote_b_contracts.py` pasa.
- No hay cambios de esquema BD.

---

### B.1 — Migración aditiva

**Archivos**
- `backend/migrations/versions/b7c8d9e0f1a2_lote_b_movimientos_wms.py` (nuevo)
- `backend/tests/integration/test_migration_lote_b.py` (nuevo)

**Cambios**
- Todo lo listado en `WMS_LOTE_B_DISENO.md`, sección 10.1.
- Sin backfill automático.
- `downgrade()` lanza `RuntimeError`.

**Pruebas**
- `alembic upgrade head` desde `empty` en BD sintética.
- Inspección de columnas, índices, triggers y vistas.
- Intento de `UPDATE` a movimiento falla.
- Reverso duplicado falla.
- Divergencia de saldo falla al confirmar.

**Terminado cuando**
- Migración aplicada solo en base sintética.
- `pytest -q backend/tests/integration/test_migration_lote_b.py` pasa.
- No se ejecutó en base real ni del piloto sin ticket.

---

### B.2 — Modelos y repositorio

**Archivos**
- `backend/app/modules/inventory/models.py`
- `backend/app/modules/inventory/repository.py` (nuevo)
- `backend/tests/inventory/test_lote_b_repository.py` (nuevo)

**Cambios**
- Modelos SQLAlchemy para `StockBalanceDetail`, `MovementOrder`, `MovementOrderLine`, `MovementTask`.
- Helpers:
  - `get_or_create_balance_locked()`
  - `get_or_create_balance_detail_locked()`
  - `lock_source_document()`
  - `lock_scope_rows()`
  - `next_delivery_seq()`
- Sin endpoints todavía.

**Pruebas**
- Creación concurrente del mismo scope no genera `UniqueViolation`.
- Orden de bloqueo determinista; prueba de dos scopes en orden inverso sin deadlock.

**Terminado cuando**
- Repositorio cubre solo operaciones de saldo y orden.
- No se modificaron servicios heredados todavía.

---

### B.3 — Entradas

**Archivos**
- `backend/app/modules/inventory/service.py`
- `backend/app/api/v1/routers/wms_movements.py` (nuevo)
- `backend/app/main.py` (registro condicional del router)
- `backend/tests/inventory/test_lote_b_receipts.py` (nuevo)

**Cambios**
- Extender `receive_stock()` con parámetros opcionales: `lot_ref_id`, `serial_id`, `location_ref_id`, `stock_state`, `movement_order_line_id`, `occurred_at`.
- Mantener llamada actual de `PurchasingService.receive()` intacta.
- Endpoint `POST /api/v1/wms/movements/receipts`.
- Validaciones de ubicación, lote, serie, restricciones y capacidad.

**Pruebas**
- Recepción con lote/serie/ubicación.
- Recepción heredada de OC sigue creando un `CostLayer` por línea.
- Reintento con misma clave no duplica movimiento ni capa de costo.

**Terminado cuando**
- Saldo agregado y detallado reconcilian.
- Pruebas heredadas de compras siguen pasando.

---

### B.4 — Salidas

**Archivos**
- `backend/app/modules/inventory/service.py`
- `backend/app/modules/inventory/wms_movement_schemas.py`
- `backend/tests/inventory/test_lote_b_issues.py` (nuevo)

**Cambios**
- `issue_enriched()` usa reserva, detalle `AVAILABLE`, lote/serie y `delivery_seq`.
- `line_net_issued_qty()` para control de autorizado.
- Endpoint `POST /api/v1/wms/movements/issues`.
- Snapshot de equipo/centro de costo/OT/solicitante.

**Pruebas**
- Los escenarios C01, C02, C03, C06, C08 y C19 de la matriz.
- Over-delivery rechazado.
- Pick desde `QUARANTINE` rechazado.

**Terminado cuando**
- Ninguna prueba concurrente produce doble salida ni saldo negativo.
- `/inventory/issues` heredado conserva su comportamiento.

---

### B.5 — Devoluciones y cuarentena

**Archivos**
- `backend/app/modules/inventory/service.py`
- `backend/app/modules/inventory/wms_movement_schemas.py`
- `backend/tests/inventory/test_lote_b_returns.py` (nuevo)

**Cambios**
- `return_issue()` con `return_of_movement_id`, `return_seq`, destino `INSPECTION/QUARANTINE`.
- `quarantine_from_available()` y `release_from_quarantine()` como pares `ADJUSTMENT_OUT/IN` con `movement_group_id`.
- Endpoint `POST /api/v1/wms/movements/returns` y `POST /api/v1/wms/movements/quarantine`.

**Pruebas**
- C15, C16 y C07.
- Devolución no revierte `line_delivered_qty`; reverso sí.
- Liberación sin aprobación rechazada.

**Terminado cuando**
- Toda devolución referencia su `ISSUE`.
- Ninguna fila no disponible es reservable o surtible.

---

### B.6 — Reversos e inmutabilidad

**Archivos**
- `backend/app/modules/inventory/service.py`
- `backend/app/api/v1/routers/wms_movements.py`
- `backend/tests/inventory/test_lote_b_reversals.py` (nuevo)

**Cambios**
- `reverse_movement()` crea `REVERSAL`, valida trigger y actualiza proyecciones.
- Endpoint `POST /api/v1/wms/movements/reversals`.
- Sin exponer ninguna edición de movimiento.

**Pruebas**
- C04, C11 y C19.
- Reverso de reverso rechazado.
- Movimiento original permanece byte-a-byte igual.

**Terminado cuando**
- Inmutabilidad verificada en base, no solo en servicio.

---

### B.7 — Kardex y reconciliación

**Archivos**
- `backend/app/api/v1/routers/wms_movements.py`
- `backend/app/modules/inventory/wms_movement_schemas.py`
- `backend/tests/inventory/test_lote_b_kardex.py` (nuevo)

**Cambios**
- Endpoints:
  - `GET /api/v1/wms/movements/kardex`
  - `GET /api/v1/wms/movements/balances`
  - `GET /api/v1/wms/movements/reconciliation`
- Filtros por dimensiones, fechas, documento, actor, equipo, centro de costo y OT.

**Pruebas**
- Kardex incluye entradas, salidas, devoluciones y reversos.
- `signed_running_qty` coincide con la suma de cantidades signadas.
- Vista de reconciliación reporta cero diferencias.

**Terminado cuando**
- Auditoría y kardex explican el mismo conjunto de hechos.

---

### B.8 — Auditoría, permisos y alcance

**Archivos**
- Routers y servicios de B.3–B.7
- `backend/app/api/v1/deps.py` si hace falta helper de alcance
- `backend/tests/security/test_lote_b_rbac.py` (nuevo)

**Cambios**
- `require_permission` en todos los endpoints nuevos.
- `AuditService.record` con `before/after`, `request_id` y correlación.
- Filtro obligatorio por `company_id`, `mining_unit_id` y `warehouse_id` según rol.
- Ningún log con credenciales o tokens.

**Pruebas**
- C14 y C20.
- Usuario sin permiso recibe `403`.
- Alcance de unidad minera respetado en kardex y saldos.

**Terminado cuando**
- Bitácora cubre entradas, salidas, devoluciones, cuarentena y reversos.

---

### B.9 — Frontend mínimo

**Archivos**
- `frontend/src/features/inventory/`
- `frontend/src/features/wms/`
- `frontend/src/api/` cliente tipado desde OpenAPI

**Cambios**
- Lista de saldos detallados con filtros.
- Formularios de entrada, salida, devolución y reverso.
- Kardex con filtros y exportación CSV local.
- Sin `fetch` directo en componentes; sin secretos en `localStorage`.

**Pruebas**
- `npm run test -- --run`
- `npm run build`

**Terminado cuando**
- UI en español, mensajes de error accionables y sin datos sensibles.

---

### B.10 — Verificación final

**Acciones**
- `pytest -q` completo: base 68 + nuevas.
- `npm run test -- --run`: base 25 + nuevas.
- `npm run build`.
- Portal local en `127.0.0.1`, smoke 30/30 si aplica.
- Revisión de `git diff`: sin secretos, sin datos reales, sin `0.0.0.0`.
- Actualizar `docs/WMS_LOTE_B_RESULTADOS.md` con evidencia.
- Commit local en español. Sin push.

**Terminado cuando**
- Todas las pruebas nuevas y heredadas pasan.
- Migración verificada de `empty` a `head`.
- Quedan documentadas limitaciones y siguiente paso (Lote C).

---

## 4. Matriz de dependencias

| Lote | Bloquea | Razón |
|---|---|---|
| B.0 | B.1 | Migración no necesita esquemas, pero sí nombres de permisos estables |
| B.1 | B.2 | Modelos deben coincidir con DDL |
| B.2 | B.3–B.7 | Servicios usan repositorio y bloqueos |
| B.3 | B.4 | Salidas consumen entradas existentes en pruebas |
| B.4 | B.5 | Devolución requiere `ISSUE` previo |
| B.5 | B.6 | Reverso sobre devolución también debe ser válido |
| B.6 | B.7 | Kardex debe mostrar reversos |
| B.7 | B.8 | Auditoría se verifica sobre datos consultables |
| B.8 | B.9 | Frontend consume permisos y endpoints finales |
| B.9 | B.10 | Verificación final requiere build listo |

---

## 5. Definición de terminado por lote

- Código compila y pasa lint/type-check disponible.
- Pruebas nuevas y existentes pasan localmente.
- Migración, si aplica, es aditiva y probada de `empty` a `head`.
- Sin secretos ni datos reales en el diff.
- Bitácora cubre acciones sensibles nuevas.
- Documentación relevante actualizada.
- Limitaciones y siguiente paso indicados explícitamente.

---

## 6. Apéndice A — Prompts para OpenCode

### Reglas comunes para todos los prompts

Aplicar siempre:

```text
Trabaja en E:\ERP_MINERO. Lee AGENTS.md, docs/WMS_LOTE_B_DISENO.md y este plan antes de cambiar código.
No modifiques CONTPAQi, GMAO, bases reales ni migraciones aplicadas.
No ejecutes DROP, TRUNCATE, DELETE masivo, alembic downgrade, push ni despliegue.
Usa datos sintéticos y datos reales solo si el usuario lo autoriza por escrito.
Server local solo en 127.0.0.1.
Agrega pruebas automatizadas por cada cambio y ejecútalas localmente.
Haz un commit local por lote con mensaje en español, imperativo y específico.
Si una regla de negocio es ambigua, pregunta; no asumas.
Reporta explícitamente qué quedó pendiente.
```

### Prompt B.0 — Contratos y bandera

```text
Aplica reglas comunes.

Implementa el lote B.0:
1. Agrega en backend/app/shared/constants.py los permisos canónicos y aliases del plan, sin quitar los existentes.
2. Asigna los nuevos permisos a los roles indicados, conservando ADMIN y los alias heredados.
3. Agrega WMS_LOTE_B_ENABLED=False en backend/app/core/config.py.
4. Crea backend/app/modules/inventory/wms_movement_schemas.py con los esquemas Pydantic v2 listados, usando Decimal y UUID, sin float.
5. Crea backend/tests/unit/test_lote_b_contracts.py con validación de esquemas y aliases.

No registres routers todavía. No toques base de datos. Ejecuta pytest -q backend/tests/unit/test_lote_b_contracts.py.
```

### Prompt B.1 — Migración aditiva

```text
Aplica reglas comunes.

Implementa el lote B.1:
1. Crea backend/migrations/versions/b7c8d9e0f1a2_lote_b_movimientos_wms.py con down_revision=a1b2c3d4e5f6.
2. Agrega únicamente: inv.stock_balance_detail, wms.movement_order, wms.movement_order_line, wms.movement_task, columnas/índices/triggers/vistas/función de backfill descritos en WMS_LOTE_B_DISENO.md sección 10.1.
3. No hagas backfill automático. No elimines columnas ni datos. downgrade() debe lanzar RuntimeError.
4. Crea backend/tests/integration/test_migration_lote_b.py: empty->head en BD sintética, inspección de objetos, prueba de inmutabilidad, reverso duplicado y reconciliación.
5. Ejecuta la migración solo contra la base sintética de pruebas.

Reporta los objetos creados y la prueba ejecutada. No ejecutes Alembic sobre bases reales.
```

### Prompt B.2 — Modelos y repositorio

```text
Aplica reglas comunes.

Implementa el lote B.2:
1. Agrega en backend/app/modules/inventory/models.py los modelos StockBalanceDetail, MovementOrder, MovementOrderLine y MovementTask alineados con la migración B.1.
2. Crea backend/app/modules/inventory/repository.py con get_or_create_balance_locked, get_or_create_balance_detail_locked, lock_source_document, lock_scope_rows y next_delivery_seq.
3. Usa INSERT ... ON CONFLICT DO NOTHING RETURNING seguido de SELECT ... FOR UPDATE; nunca SELECT previo para decidir inserción.
4. Ordena siempre agregado antes que detalle y maestros antes que saldos.
5. Crea backend/tests/inventory/test_lote_b_repository.py con creación concurrente del mismo scope y dos scopes en orden inverso.
6. Ejecuta pytest -q backend/tests/inventory/test_lote_b_repository.py.

No expongas endpoints ni modifiques servicios heredados todavía.
```

### Prompt B.3 — Entradas

```text
Aplica reglas comunes.

Implementa el lote B.3:
1. Extiende InventoryService.receive_stock con parámetros opcionales lot_ref_id, serial_id, location_ref_id, stock_state, movement_order_line_id y occurred_at, con defaults None.
2. Sincroniza inv.stock_balance e inv.stock_balance_detail en la misma transacción y escribe scope_balance_after_qty.
3. Valida ubicación receivable/ACTIVE, lote no BLOCKED/EXPIRED, serie no duplicada, capacidad y restricciones.
4. Conserva exactamente la llamada actual de PurchasingService.receive y la creación de CostLayer por línea.
5. Crea backend/app/api/v1/routers/wms_movements.py con POST /wms/movements/receipts, protegido y condicionado a WMS_LOTE_B_ENABLED.
6. Registra el router en backend/app/main.py sin quitar los routers actuales.
7. Crea y ejecuta backend/tests/inventory/test_lote_b_receipts.py.

No cambies claves de idempotencia existentes.
```

### Prompt B.4 — Salidas

```text
Aplica reglas comunes.

Implementa el lote B.4:
1. Agrega InventoryService.line_net_issued_qty y un método issue_enriched en backend/app/modules/inventory/service.py.
2. Consume reservas activas FIFO bajo FOR UPDATE, valida stock_state=AVAILABLE, ubicación pickable, lote/serie elegible y delivery_seq único.
3. Descuenta agregado y detalle, consume reservation.consumed_qty, escribe serial.status=ISSUED y crea movimiento ISSUE/OUT con snapshot de requisición.
4. Usa net_issued para la regla de no sobreentrega. Mantén line_delivered_qty heredado intacto.
5. Agrega POST /wms/movements/issues.
6. Crea y ejecuta backend/tests/inventory/test_lote_b_issues.py con escenarios C01, C02, C03, C06, C08 y C19.

No modifiques /api/v1/inventory/issues ni sus claves por defecto.
```

### Prompt B.5 — Devoluciones y cuarentena

```text
Aplica reglas comunes.

Implementa el lote B.5:
1. Agrega return_issue() con return_of_movement_id, return_seq, destino INSPECTION en ubicación QUARANTINE y validación de límite acumulado.
2. Agrega quarantine_from_available() y release_from_quarantine() como pares ADJUSTMENT_OUT/ADJUSTMENT_IN unidos por movement_group_id.
3. La liberación exige aprobación y audit actor; nunca actualices stock_state sin movimiento.
4. Agrega POST /wms/movements/returns y POST /wms/movements/quarantine.
5. Crea y ejecuta backend/tests/inventory/test_lote_b_returns.py con C15, C16 y C07.

Verifica que una devolución no reduzca line_delivered_qty y que un reverso sí lo haga.
```

### Prompt B.6 — Reversos e inmutabilidad

```text
Aplica reglas comunes.

Implementa el lote B.6:
1. Agrega InventoryService.reverse_movement() creando un REVERSAL con dirección opuesta, cantidad igual y mismo item/warehouse/lote/serie/ubicación.
2. Ajusta agregado, detalle y net_issued en la misma transacción.
3. Agrega POST /wms/movements/reversals con motivo y aprobación cuando aplique.
4. Confía en los triggers de la migración B.1 para inmutabilidad, reverso duplicado y reverso encadenado.
5. Crea y ejecuta backend/tests/inventory/test_lote_b_reversals.py con C04, C11 y C19.

No expongas ningún endpoint de edición o borrado de movimientos.
```

### Prompt B.7 — Kardex y reconciliación

```text
Aplica reglas comunes.

Implementa el lote B.7:
1. Agrega GET /wms/movements/kardex, GET /wms/movements/balances y GET /wms/movements/reconciliation usando las vistas de B.1.
2. Soporta filtros por item, warehouse, location, lot, serial, fecha, tipo, documento, actor, equipo, centro de costo y work_order_no.
3. Usa esquemas Pydantic de B.0; no devuelvas objetos SQLAlchemy crudos.
4. Crea y ejecuta backend/tests/inventory/test_lote_b_kardex.py.
5. Verifica signed_running_qty y cero diferencias en reconciliación.

No dupliques hechos en tablas nuevas.
```

### Prompt B.8 — Auditoría, permisos y alcance

```text
Aplica reglas comunes.

Implementa el lote B.8:
1. Cablea require_permission con los permisos de B.0 en todos los endpoints de B.3 a B.7.
2. Registra AuditService.record para entrada, salida, devolución, cuarentena, liberación y reverso, con before/after y request_id.
3. Aplica filtro de alcance por company_id, mining_unit_id, department_id y warehouse_id según el rol.
4. Asegura que ningún log incluya contraseñas, tokens ni cadenas de conexión.
5. Crea y ejecuta backend/tests/security/test_lote_b_rbac.py con C14 y C20.

La UI no es autoridad; el backend sí.
```

### Prompt B.9 — Frontend mínimo

```text
Aplica reglas comunes.

Implementa el lote B.9:
1. Crea frontend/src/features/inventory/ y frontend/src/features/wms/ con listado de saldos detallados y kardex.
2. Agrega formularios de entrada, salida, devolución y reverso usando el cliente API tipado desde OpenAPI.
3. No hagas fetch directo en componentes; no guardes secretos en localStorage.
4. Usa español, terminología técnica mínima y errores accionables.
5. Ejecuta npm run test -- --run y npm run build.

No expongas acciones que el backend no autorice.
```

### Prompt B.10 — Verificación final

```text
Aplica reglas comunes.

Ejecuta el cierre del Lote B:
1. pytest -q completo, incluyendo las 68 pruebas base y las nuevas.
2. npm run test -- --run y npm run build.
3. Portal local en 127.0.0.1, smoke 30/30 si el script existe.
4. Revisa git diff: sin secretos, datos reales, 0.0.0.0 ni cambios destructivos.
5. Crea docs/WMS_LOTE_B_RESULTADOS.md con evidencia, comandos, conteos y limitaciones.
6. Haz commit local con mensaje en español e imperativo. No hagas push.

Reporta explícitamente lo pendiente para el Lote C.
```

---

## 7. Prohibiciones del Lote B

- No `DROP`, `TRUNCATE`, `DELETE` masivo ni `downgrade`.
- No editar ni borrar `inv.stock_movement`.
- No crear un segundo inventario oficial.
- No conectar a CONTPAQi ni GMAO.
- No exponer puertos ni usar `0.0.0.0`.
- No guardar contraseñas, tokens ni secretos.
- No usar `float` para cantidades ni dinero.
- No afirmar terminado sin pruebas ejecutadas.
