# WMS avanzado — Arquitectura propuesta

**Fecha:** 2026-11-18

**Estado:** DISEÑO. No implica implementación.

**Aplica sobre:** ERP MINERO INTEGRAL, head `f4a7c1e2b3d6`, monolito modular FastAPI + React.
**Principio rector:** un solo ledger de inventario (`inv.stock_movement`) y CONTPAQi como sistema oficial.

---

## 1. Visión

Construir una capa WMS propia que transforme el almacén operativo actual en un almacén minero trazable por ubicación, lote, serie, documento, responsable y costo, sin crear un segundo inventario oficial ni modificar sistemas externos.

```text
Navegador / móvil
   │  API REST del mismo ERP (/api/v1)
   ▼
Routers WMS  →  Servicios de dominio  →  SQLAlchemy  →  PostgreSQL
   │                 │                      │
   │                 ├─ numeración, idempotencia, auditoría, outbox
   │                 └─ RBAC + alcance company/mining_unit/department/warehouse
   ▼
Ledger inv.stock_movement  →  cost.cost_posting  →  intg.outbox_event
   ▲
   └─ órdenes, tareas, conteos, préstamos y recomendaciones son documentos de apoyo;
      nunca sustituyen al movimiento de inventario.
```

---

## 2. Principios arquitectónicos WMS

1. **Ledger único.** Todo cambio físico termina en `inv.stock_movement`. Las tablas nuevas son documentos, tareas o proyecciones.
2. **Maestro físico separado del saldo.** Artículo, lote, serie y ubicación son maestros; `inv.stock_balance` es la proyección cuantitativa.
3. **Documento antes que movimiento.** Toda entrada, salida, traspaso o ajuste nace de un documento con folio único.
4. **Orquestación única por operación.** Una orden de movimiento agrupa tareas, pero el efecto contable es atómico.
5. **Ubicación como primera clase.** `location_id` deja de ser un UUID opaco y apunta a `mdm.storage_location`.
6. **Lote y serie como primera clase.** `lot_tracked`/`serial_tracked` exigen referencias reales.
7. **Concurrencia explícita.** Bloqueo determinista por `(warehouse_id, item_id, lot_id, location_id)`.
8. **Append-only.** Ningún movimiento, asiento o evento se actualiza; las correcciones son contrapartidas.
9. **IA asesora.** Las recomendaciones no crean movimientos ni autorizan operaciones.
10. **Integración pasiva.** CONTPAQi y GMAO nunca se escriben directamente.

---

## 3. Mapa de dominios

| Dominio | Estado | Responsabilidad WMS |
|---|---|---|
| `identity` | Existente | Usuarios, roles, permisos y sesiones |
| `organization` | Existente | Empresa, unidad minera, departamento, almacén, empleado |
| `master_data` | Extender | Artículos avanzados, UOM, conversiones, familias, proveedores, lotes, series, ubicaciones |
| `documentation` | Existente | Numeración, registro de documento, eventos, idempotencia |
| `requisitions` | Existente | Solicitud de materiales y autorización por partida |
| `workflow` | Existente | Pasos y decisiones de aprobación |
| `inventory` | Extender | Saldos, movimientos, reservas, órdenes, tareas, traspasos, conteos, ajustes |
| `purchasing` | Existente | OC, recepciones y futura factura/triple match |
| `maintenance` | Extender | Equipos, OT y herramientas retornables |
| `costing` | Extender | Capas, asientos, asignaciones y objetos de costo |
| `integrations` | Extender | Mapeos, staging, batches, conciliación y eventos |
| `audit` | Existente | Bitácora inmutable |
| `wms` | Propuesto, delgado | Sólo orquestación, móvil, sugerencias y analítica; **nunca saldos** |

### 3.1 ¿Por qué un esquema `wms` delgado?

Evita mezclar maestros físicos con reglas de negocio temporal:

- `mdm`: qué existe.
- `inv`: cuánto existe y cómo se movió.
- `wms`: qué tarea hay que hacer, qué sugiere el sistema y qué conclusión tomó el humano.

Si no se aprueba el esquema `wms`, esas tablas pueden ubicarse en `inv` con prefijo `wms_`; la decisión queda pendiente.

---

## 4. Capas y dependencias

```text
frontend/src/features/warehousing/*        UI en español, RTL-compatible
frontend/src/api/client.ts                 Cliente tipado, CSRF, mismo origen
        │
backend/app/api/v1/routers/*               Validación Pydantic + require_permission
        │
backend/app/modules/<dominio>/service.py   Casos de uso transaccionales
        │
backend/app/modules/<dominio>/models.py    SQLAlchemy 2 declarativo
        │
PostgreSQL: mdm / inv / cost / intg / aud / wms
```

Reglas:

- Los routers no contienen reglas de negocio.
- Los modelos de dominio no importan FastAPI.
- Un servicio de otro módulo se expone por interfaz o evento, nunca accediendo a sus tablas.
- `wms` puede leer `inv` para proyecciones, pero escribe inventario únicamente mediante `InventoryService`.

---

## 5. Flujo transversal de movimiento

```text
Documento origen
  (REQ / OC /devolución / traspaso / conteo / préstamo)
        │
        ▼
Orden de movimiento (wms.movement_order)
  - tipo, almacén, prioridad, solicitante, autorizador
        │
        ▼
Tarea(s) de almacén (wms.movement_task)
  - picking / putaway / conteo / carga / descarga
  - operario asignado, estado, evidencia
        │
        ▼
Validación de reglas
  - permiso y alcance
  - lote/serie/ubicación
  - disponible = on_hand - reserved
  - FEFO o política aprobada
  - idempotencia
        │
        ▼
inv.stock_movement (append-only)
  + actualización bloqueada de inv.stock_balance
  + cost.cost_posting en la misma transacción
  + aud.audit_log + intg.outbox_event
        │
        ▼
Cierre documental e historial
```

Si una tarea falla, se conserva el intento y se genera una contrapartida o reversión; no se borra el registro previo.

---

## 6. Componentes reutilizables

| Componente | Ubicación actual | Uso WMS |
|---|---|---|
| `next_document_number()` | `backend/app/shared/numbering.py:62` | Folios de entradas, salidas, traspasos, conteos, préstamos y ajustes |
| `record_document_event()` | `backend/app/shared/numbering.py:96` | Historial de estados de cada documento |
| `acquire()` / `complete()` | `backend/app/shared/idempotency.py:24,70` | Reintentos seguros de móvil, importaciones y movimientos |
| `emit()` | `backend/app/shared/events.py` | Outbox transaccional |
| `AuditService.record()` | `backend/app/modules/audit/service.py:38` | Bitácora inmutable |
| `InventoryService.reserve/issue/...` | `backend/app/modules/inventory/service.py` | Núcleo de reservas y entregas |
| `PurchasingService.receive` | `backend/app/modules/purchasing/service.py:229` | Entradas por OC y capas de costo |
| `IdentityService.has_permission/assert_*` | `backend/app/modules/identity/service.py:251+` | RBAC y alcance |
| `require_permission()` | `backend/app/api/v1/deps.py:81` | Guardias de endpoint |
| Cliente API con CSRF | `frontend/src/api/client.ts:55+` | Base para pantallas WMS y móvil web |

---

## 7. Concurrencia e idempotencia

### 7.1 Orden de bloqueo

Para cualquier operación que toque varios saldos:

1. Ordenar almacenes por UUID.
2. Dentro de cada almacén, ordenar artículos por UUID.
3. Luego lote y ubicación por UUID.
4. Aplicar `SELECT … FOR UPDATE` en ese orden.
5. Registrar la clave de idempotencia antes de producir efectos.

Esto evita deadlocks entre traspasos y conteos concurrentes.

### 7.2 Clave de idempotencia

Formato recomendado:

```text
SHA256(company_id | source_type | source_id | line_id | operation | attempt)
```

Reglas:

- La clave es única en `doc.idempotency_record` y en la tabla de hechos.
- Si la operación ya terminó, se devuelve la entidad existente; no se duplica.
- Si la clave pertenece a otra operación, se rechaza con 409.
- Los reintentos móviles usan la misma clave hasta recibir confirmación.

### 7.3 Reversiones

- Toda reversión referencia `reversal_of_id`.
- La reversión crea un movimiento nuevo de signo opuesto.
- Se exige motivo, actor, autorizador cuando aplique y auditoría.
- Nunca se modifica ni elimina el movimiento original.

---

## 8. RBAC y alcance

### 8.1 Principios

- El backend es la autoridad; la UI sólo oculta acciones.
- Todo endpoint WMS usa `require_permission`.
- El alcance se valida contra `company_id`, `mining_unit_id`, `department_id` y `warehouse_id`.
- Un usuario de una unidad minera no puede consultar ni mover stock de otra.

### 8.2 Permisos propuestos

| Permiso | Uso |
|---|---|
| `catalog.view` / `catalog.manage` | Catálogo y maestros |
| `warehouse.location.view` / `warehouse.location.manage` | Ubicaciones y QR |
| `warehouse.stock.view` | Consulta de disponibilidad por ubicación/lote |
| `wms.receipt.create` / `wms.receipt.approve` | Entradas |
| `wms.issue.create` / `wms.issue.approve` | Salidas |
| `wms.transfer.create` / `wms.transfer.approve` / `wms.transfer.receive` | Traspasos |
| `wms.count.create` / `wms.count.reconcile` | Conteos y diferencias |
| `wms.tool.loan` / `wms.tool.return` | Herramientas |
| `cost.posting.view` / `cost.posting.approve` | Costos |
| `wms.replenishment.view` | Reabastecimiento |
| `wms.ai.explanation.view` | Explicaciones de IA |

Los alias en español se registrarán en `constants.py` para mantener compatibilidad con el esquema actual.

---

## 9. Observaciones, trazabilidad y proyecciones

### 9.1 Kardex

El kardex será una **vista/proyección** sobre `inv.stock_movement`, no una tabla que duplique hechos:

```text
movimiento → artículo, almacén, ubicación, lote, serie,
             cantidad, dirección, saldo posterior,
             costo unitario, documento, actor, fecha
```

Debe permitir filtros por item, warehouse, location, lot, serial, fecha, tipo de movimiento y documento.

### 9.2 Cantidades derivadas

Se implementará una vista o funciones de servicio equivalentes a `req.v_requisition_line_quantities` (`MODELO_DATOS.md:334-374`), hoy documentada pero no creada.

### 9.3 Analítica

Los KPIs se calculan desde proyecciones de lectura:

- exactitud de inventario;
- rotación y días de cobertura;
- cumplimiento de surtido;
- material sin movimiento;
- consumo por equipo/área;
- diferencias por conteo;
- traspasos pendientes;
- costo valorizado.

Ninguna proyección escribe en tablas de hechos.

---

## 10. Captura móvil y mapa visual

- PWA/React sobre el mismo backend; sin aplicación nativa en el primer incremento.
- Escaneo QR/código de barras mediante cámara o lector; el resultado se envía como parámetro de búsqueda o validación.
- La evidencia fotográfica se almacena fuera de la BD, con SHA-256 y ruta controlada, similar a `req.requisition_attachment`.
- Offline: no en Lote A. Si se habilita, cada intento llevará idempotencia y confirmación posterior; el dispositivo nunca será fuente oficial de stock.
- Plano 2D: vista SVG por almacén con zonas y ubicaciones; 3D queda como evolución, no compromiso del diseño inicial.

---

## 11. Inteligencia artificial

```text
Datos sintéticos / históricos autorizados
        │
 Features (consumo, lead time, estacionalidad, ubicación)
        │
 Modelo / regla explicable
        │
 Recomendación + confianza + motivo + datos de soporte
        │
 Revisión humana
        │
 Documento operativo normal (si se aprueba)
```

Restricciones:

- La IA no crea movimientos, reserve ni autorice por sí sola.
- Toda recomendación guarda entrada, salida, versión del modelo y explicación.
- Sin datos reales sin autorización por escrito.
- Si no hay volumen suficiente, se usan reglas deterministas y se reporta “datos insuficientes”.

---

## 12. Integración con CONTPAQi

- Sin conexión directa a su base.
- `intg.external_mapping` relaciona códigos internos y externos.
- `intg.integration_batch` + `intg.integration_staging` registran archivos controlados: nombre, hash, tamaño, usuario y resultado.
- `intg.outbox_event` emite propuestas de sincronización; un despachante autorizado las procesa.
- `intg.inbox_event` registra confirmaciones con `event_id` único.
- Las existencias y costos se concilian, pero no se autoajusta el sistema oficial.

Detalle en `docs/WMS_MATRIZ_INTEGRACION_CONTPAQI.md`.

---

## 13. Seguridad y operación

- Desarrollo y piloto en `127.0.0.1`; LAN sólo con autorización.
- HTTPS, cookies `Secure`/`HttpOnly`/`SameSite`, `ALLOWED_HOSTS`, CORS vacío y CSRF para futura intranet.
- Logs de acceso, errores, auditoría y operaciones; sin secretos.
- PostgreSQL no expuesto a usuarios finales.
- Respaldo lógico y restauración de prueba en base nueva; nunca sobre la original.

---

## 14. Decisiones arquitectónicas pendientes

| ID | Decisión | Recomendación |
|---|---|---|
| AD-01 | Esquema `wms` vs tablas `inv_` | Aprobar `wms` delgado para orquestación |
| AD-02 | Lotes/series obligatorios | Por artículo, con validación en servicio al crear movimientos |
| AD-03 | Jerarquía de ubicación | Zona → pasillo → anaquel → posición; almacén como raíz |
| AD-04 | Política de costos | Sólo método autorizado por contabilidad; no inventar reglas |
| AD-05 | Herramientas | Extender `mnt` con entidades de préstamo; no crear almacén paralelo |
| AD-06 | Captura móvil offline | Diferir hasta exista idempotencia probada y RBAC por almacén |
| AD-07 | Despachante de outbox | Diseñar worker idempotente antes de integración real |
| AD-08 | Vistas vs funciones | Crear vistas derivadas sobre `inv`; ninguna tabla de duplicated facts |

---

## 15. Criterios de aceptación arquitectónica

- Un solo `inv.stock_movement` por efecto físico.
- Toda operación sensible genera documento, idempotencia, auditoría y evento.
- Ningún endpoint WMS omite RBAC/alcance.
- Ninguna tabla WMS duplica `on_hand_qty` ni `reserved_qty` como verdad oficial.
- Todas las migraciones son aditivas y pasan `empty → head`.
- La UI usa rutas relativas y cliente tipado.
- La IA no escribe inventario.
- No se declarará producción sin TLS, autorización, respaldo probado y triple match resuelto.
