# Fase 4 — Circuito integral de requisiciones: resultados

**Fecha:** 2026-11-18
**Ruta física:** `E:\ERP_MINERO`
**Estado:** IMPLEMENTADA Y VERIFICADA localmente sobre PostgreSQL 17.12 real. **No declarada apta para producción**: el triple match OC–recepción–factura continúa pendiente (§7).
**Commit previo de recuperación:** `6a05492 Agrega identidad, sesiones y RBAC de la Fase 3` (sin push).
**Commit local de la Fase 4:** registrado en el historial local (sin push; ver `git log -1`).
**Alcance:** PASO 0 a PASO 9 del plan de la Fase 4. No se modificaron CONTPAQi Comercial Premium 11.5.1, Sierra Madre GMAO ni sistemas de la mina.

---

## 1. Resumen ejecutivo

- Captura completa con folio único `REQ-LAG-AAAA-NNNNNN`, fecha de creación, unidad minera y compañía derivadas del departamento, departamento, solicitante, equipo, OT externa opcional, centro de costo, justificación, prioridad (Normal/Alta/Crítica), fecha requerida, observaciones y partidas consecutivas con código, descripción, UOM y cantidades `NUMERIC(18,6)`.
- Los borradores son editables y solo por su autor o un administrador; se rechazan partidas vacías, descripción corta y cantidades no positivas.
- Envío a autorización con solicitud y paso de aprobación; decisión por partida con motivo obligatorio en rechazos, actor, fecha/hora e historial. Bloqueadas la autoautorización, las decisiones duplicadas y el acceso entre departamentos. No existe aprobación automática por importe.
- Reservas parciales/completas transaccionales sobre saldos bloqueados con `SELECT ... FOR UPDATE`; anti-sobrereserva por partida y por existencia; vencimiento explícito a 7 días con barrido controlado; liberación al cancelar o rechazar. Las reservas **no** descuentan el stock físico.
- Idempotencia atómica en `doc.idempotency_record` mediante `INSERT ... ON CONFLICT DO NOTHING RETURNING` dentro de la misma transacción del cambio de negocio, con clave persistida y confirmación de la entidad resultante.
- Faltantes calculados como `autorizado - entregado - reservado - comprado`; OC generadas desde faltantes reales, sin duplicados, con cancelación que devuelve el faltante y validación de compañía/unidad.
- Entregas parciales/completas con movimiento `ISSUE`, consumición ordenada de reservas, descuento atómico de existencia y cierre automático de la requisición solo cuando todas las partidas están conciliadas o canceladas.
- Adjuntos controlados fuera de la base (`var/attachments`, ignorado por Git) con nombre lógico, nombre físico, MIME, tamaño, SHA-256 y responsable; solo PDF/JPG/PNG hasta 5 MiB.
- API versionada bajo `/api/v1` con RBAC backend; UI React/TypeScript con captura, filtros, bandeja de autorizaciones, almacén, compras, adjuntos y seguimiento.
- **60 pruebas backend** (42 regresiones + 18 nuevas, con PostgreSQL real y concurrencia mediante conexiones independientes) y **7 pruebas frontend**, todas en verde.

## 2. Inventario y matriz inicial (PASO 1)

| Dominio | Estado previo | Hallazgo | Acción en Fase 4 |
|---|---|---|---|
| Captura de requisiciones | Existente | Sin prioridad completa, OT, adjuntos, fecha requerida ni cantidades derivadas; folio presente | Ampliada; borrador editable; partidas consecutivas; validación estricta |
| Autorización | Existente | Bandeja con decisión solo global; autoautorización cubierta en Fase 3; sin motivo por partida ni historial de decisiones | Decisiones por partida, motivo, actor/timestamp, roles `APPROVER_ROLE_CODES`, alcance y decisiones duplicadas bloqueadas |
| Reservas | Existente | Idempotencia `SELECT`-then-`INSERT` no atómica; sin vencimiento; anti-sobrereserva insuficiente | Idempotencia atómica, bloqueo de saldo y partida, expiración a 7 días, liberación transaccional |
| Faltantes y compras | Existente | OC canceladas seguían descontando el faltante; faltaban cancelación, validación de compañía e idempotencia atómica | Cálculo excluye OC canceladas/cerradas; cancelación de OC; idempotencia atómica; validación de maestros |
| Entregas | Existente | Movimiento presente; cierre automático y conciliación incompletos | Entrega con reserva activa, movimiento `ISSUE`, cierre solo si todas las partidas están conciliadas |
| Seguimiento | Existente | Sin filtros combinables ni cantidades derivadas | Filtros por folio, estado, prioridad, departamento, equipo y rango de fechas; `pending_qty` derivado |
| Permisos | Existente | Sin código `requisition.cancel` | Agregados `requisition.cancel`, alias `requisiciones.cancelar` y rol `APROBADOR` como cancelador |
| Pruebas | 42 backend / 7 frontend | Sin cobertura de concurrencia, vencimiento ni cierre | 18 pruebas nuevas con PostgreSQL real y conexiones independientes |

Justificación de migración: se requieren dos tablas nuevas (registro de idempotencia y metadatos de adjuntos), una columna opcional (`work_order_no`) y restricciones de base para invariantes de cantidades. Ninguna operación elimina datos.

## 3. Cambios en la base de datos

Migración aditiva `f4a7c1e2b3d6` (`down_revision = f3a9c1d7b2e4`), aplicada en `erp_minero_dev` y `erp_minero_test`.

| Objeto | Cambio |
|---|---|
| `doc.idempotency_record` | Nueva. `UNIQUE(idempotency_key)`, `CHECK status IN ('IN_PROGRESS','COMPLETED')`, `entity_id`, `request_id`, `created_at`, `completed_at` |
| `req.requisition.work_order_no` | Columna nullable, referencia a OT externa; no se crea entidad OT local |
| `req.requisition_attachment` | Nueva. `stored_name` único, `CHECK size_bytes > 0`, FK a requisición y usuario, SHA-256 e `created_at`; sin `AuditMixin` |
| `req.requisition_line` | `CHECK cancelled_qty <= requested_qty` y `CHECK authorised_qty <= requested_qty - cancelled_qty` |
| `inv.stock_reservation` | Índice `ix_stock_reservation_expiry` sobre `(expires_at, status)` |

- Tablas por esquema después de la migración: `seg 8, org 5, mdm 3, doc 5, req 3, wfl 3, inv 3, pur 4, mnt 1, cost 2, intg 3, aud 1` = **41** (39 de la Fase 3 + 2 nuevas).
- `downgrade()` lanza `RuntimeError` por política: no se eliminan datos ni auditoría.
- Tipos monetarios y de cantidad permanecen en `NUMERIC`; timestamps en `TIMESTAMPTZ`.

## 4. Backend

| Archivo | Cambio principal |
|---|---|
| `app/shared/idempotency.py` (nuevo) | Helper `acquire()`/`complete()` con inserción atómica y verificación de operación; errores `409`/`422` sin exponer secretos |
| `app/modules/documentation/models.py` | Modelo `IdempotencyRecord` |
| `app/modules/requisitions/models.py` | `work_order_no` y modelo `RequisitionAttachment` (solo `id` y `created_at`, append-only) |
| `app/modules/requisitions/schemas.py` | Entradas de captura/borrador/decisión/cancelación y salidas con cantidades `reserved`, `purchased`, `received`, `delivered`, `pending` |
| `app/modules/requisitions/service.py` | Captura, contexto por departamento, validación de partidas, edición de borrador, envío, decisión por partida, cancelación, historial y adjuntos; derivación de cantidades desde tablas de detalle |
| `app/modules/inventory/service.py` | Idempotencia atómica, reserva/entrega transaccional, anti-sobrereserva, vencimiento, liberación por cancelación/rechazo, recepción de stock y cierre automático sin sobrescribir partidas canceladas |
| `app/modules/purchasing/service.py` | OC desde faltantes con idempotencia atómica, exclusión de OC canceladas/cerradas, validación de compañía/unidad, cancelación de OC y recepciones con movimientos y capas de costo |
| `app/modules/inventory/schemas.py`, `app/modules/purchasing/schemas.py` | `ExpirationResult`, clave de idempotencia de OC y esquema de cancelación de OC |
| `app/api/v1/routers/requisitions.py` | Endpoints de captura, borrador, envío, decisión, cancelación, historial, adjuntos y descarga; filtros y alcance departamental |
| `app/api/v1/routers/inventory.py` | `POST /inventory/reservations/expire` y contratos de reserva/entrega |
| `app/api/v1/routers/purchasing.py` | `POST /purchases/{id}/cancel` y propagación de idempotencia |
| `app/shared/constants.py` | `requisition.cancel`, alias `requisiciones.cancelar`, `APPROVER_ROLE_CODES` |
| `app/core/config.py` | `ATTACHMENT_STORAGE_DIR` y `ATTACHMENT_MAX_BYTES` (5 MiB) |
| `migrations/versions/f4a7c1e2b3d6_fase4_requisiciones.py` (nuevo) | Migración aditiva descrita en §3 |
| `tests/test_phase4_requisiciones.py` (nuevo) | 18 pruebas de Fase 4 |
| `tests/conftest.py` | Reinicio de la base sintética de pruebas al inicio de sesión; las pruebas que confirman transacciones no contaminan a las que revierten |
| `tests/test_postgres_phase2.py` | Acepta la nueva revisión `f4a7c1e2b3d6` |

## 5. Frontend

| Archivo | Cambio |
|---|---|
| `src/api/types.ts` | Tipos de requisición, partidas, filtros, historial, adjuntos, disponibilidad, reservas y movimientos |
| `src/api/client.ts` | Operaciones nuevas (borrador, decisión, cancelación, historial, adjuntos, expiración, cancelación de OC) y `attachmentUrl`; mismas credenciales de sesión y CSRF de la Fase 3 |
| `src/features/requisitions/Requisitions.tsx` | Formulario completo con partidas editables, prioridad Normal/Alta/Crítica, OT, adjuntos, cancelación, filtros y seguimiento; botones deshabilitados durante envío |
| `src/features/inventory/Inventory.tsx` | Disponibilidad, reserva y entrega con clave de idempotencia, vencimiento de reservas y kardex |
| `src/features/purchases/Purchases.tsx` | OC desde faltantes, aprobación, recepción parcial y cancelación de OC |

Se reutilizaron `features/approvals/Approvals.tsx` (bandeja con decisión global) y `features/dashboard/Dashboard.tsx` (contadores por estado) sin modificarlos.

## 6. Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m pytest -q
python -m ruff check .
python -m mypy app
python -m alembic current

cd E:\ERP_MINERO\frontend
npm.cmd run build
npm.cmd run test -- --run

cd E:\ERP_MINERO
git diff --check
```

| Verificación | Resultado |
|---|---|
| `python -m pytest -q` | **60 passed** (42 regresiones + 18 nuevas), código 0; ejecutado dos veces con mismo resultado |
| `python -m ruff check .` | `All checks passed!` |
| `python -m mypy app` | `Success: no issues found in 62 source files` |
| `python -m alembic current` | `f4a7c1e2b3d6 (head)` en ambas bases |
| `npm.cmd run build` | Correcto; `dist/assets/index-YvOHWueC.js` 218.21 kB (gzip 66.70 kB), 2.69 s |
| `npm.cmd run test -- --run` | **7 passed** (2 archivos) |
| `git diff --check` | Sin errores de whitespace; solo avisos LF→CRLF de Git en Windows |
| Revisión de secretos | Sin coincidencias de contraseñas, tokens ni cadenas con credenciales en el diff |

Detalle de las 18 pruebas: `docs/EVIDENCIA_FASE4.md`. Contratos y estados: `docs/FLUJO_REQUISICIONES.md`.

## 7. Limitaciones y siguiente paso

- **Triple match OC–recepción–factura no implementado.** Las recepciones generan entrada de inventario y capa de costo, pero no hay conciliación con factura. Mientras no exista, el circuito no debe usarse para producción.
- **Cadena `empty -> head` no verificada en base nueva.** El usuario `erp_minero_app` carece de permiso `CREATEDB` (`psycopg.errors.InsufficientPrivilege`). Se verificó la revisión y el esquema resultante en las bases existentes; la verificación desde cero queda pendiente de un rol con `CREATEDB`. El script temporal usado para el intento fue retirado del repositorio.
- La bandeja de autorizaciones de la UI solo ofrece autorizar/rechazar todas las partidas; la decisión parcial por partida está disponible en la API pero aún no en esa pantalla.
- El panel "Órdenes de compra" del dashboard muestra `—` (comportamiento previo a la Fase 4).
- La validación estricta de maestros por unidad minera se mantuvo a nivel de compañía para no romper la compatibilidad con las pruebas de la Fase 3; la restricción por unidad sí se aplica en la autorización.
- Los cambios de Fase 4 quedaron en un commit local (27 archivos); no se hizo `git push`, tag ni despliegue.
- No se conectó a CONTPAQi, Sierra Madre GMAO ni al servidor de la mina. CONTPAQi sigue siendo el inventario oficial; el ERP mantiene un espejo operativo.
- Siguiente paso recomendado: revisar y commitear la Fase 4 localmente, dotar de `CREATEDB` a un rol de verificación para validar `empty -> head`, implementar el triple match y habilitar la decisión parcial en la bandeja de autorizaciones antes de cualquier uso en producción.
