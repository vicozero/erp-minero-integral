# Evidencia de ejecución — Fase 4

**Fecha:** 2026-11-18
**Entorno:** Windows / PowerShell, PostgreSQL 17.12 real (`erp_minero_dev`, `erp_minero_test`), FastAPI + SQLAlchemy 2, React + Vite + Vitest.
**Regla cumplida:** todos los comandos se ejecutaron localmente; no se hizo `git push`, despliegue ni conexión a sistemas externos.

---

## 1. Resumen de comandos y resultados reales

| Comando | Directorio | Salida | Código |
|---|---|---|---:|
| `python -m pytest -q` | `backend` | `............................................................ [100%]` → 60 pruebas | 0 |
| `python -m pytest -q tests/test_phase4_requisiciones.py` | `backend` | `.................. [100%]` → 18 pruebas nuevas | 0 |
| `python -m ruff check .` | `backend` | `All checks passed!` | 0 |
| `python -m mypy app` | `backend` | `Success: no issues found in 62 source files` | 0 |
| `python -m alembic current` | `backend` | `f4a7c1e2b3d6 (head)` | 0 |
| `npm.cmd run build` | `frontend` | `✓ built in 2.69s`; JS 218.21 kB (gzip 66.70 kB) | 0 |
| `npm.cmd run test -- --run` | `frontend` | `Test Files 2 passed (2)`, `Tests 7 passed (7)` | 0 |
| `git diff --check` | raíz | Sin errores de whitespace; solo avisos `LF will be replaced by CRLF` | 0 |

La suite completa se ejecutó dos veces con el mismo resultado (60 passed, código 0). El único aviso de Python es `StarletteDeprecationWarning` de `fastapi.testclient` con `httpx` y el aviso de `HTTP_422_UNPROCESSABLE_ENTITY` (deprecado en favor de `HTTP_422_UNPROCESSABLE_CONTENT`); ninguno afecta el resultado. En PowerShell se usa `npm.cmd` porque la política local bloquea `npm.ps1`.

## 2. Separación de pruebas nuevas y regresiones

Conteo real de `python -m pytest -o addopts= --collect-only -q`:

| Archivo | Pruebas | Clasificación |
|---|---:|---|
| `tests/test_concurrency.py` | 1 | Regresión Fase 2 |
| `tests/test_inventory.py` | 6 | Regresión Fase 2 |
| `tests/test_phase3_auth_rbac.py` | 16 | Regresión Fase 3 |
| `tests/test_postgres_phase2.py` | 8 | Regresión Fase 2 |
| `tests/test_purchases.py` | 5 | Regresión Fase 2 |
| `tests/test_requisitions.py` | 6 | Regresión Fase 2 |
| **Subtotal regresiones** | **42** | Todas conservadas y passing |
| `tests/test_phase4_requisiciones.py` | 18 | **Nuevas Fase 4** |
| **Total** | **60** | `pytest -q` → 60 passed |

Frontend: `src/App.test.tsx` (4 pruebas) + `src/api/client.test.ts` (3 pruebas) = 7 pruebas, sin cambios en su número.

## 3. Las 18 pruebas nuevas

Todas usan PostgreSQL real. Las pruebas de concurrencia usan `ThreadPoolExecutor(max_workers=2)` con una `Session` por hilo sobre el motor compartido, y claves de idempotencia únicas por ejecución (`uuid.uuid4()`).

| # | Prueba | Comportamiento verificado | Resultado |
|---:|---|---|---|
| 1 | `test_folio_unico_y_partidas_consecutivas` | Folio `REQ-LAG-…`, partidas `line_no` 1..n, cantidades `NUMERIC`, compañía/unidad derivadas del departamento | PASSED |
| 2 | `test_captura_rechaza_partidas_vacias_y_cantidades_no_positivas` | Lista vacía y cantidad `0`/negativa → `422`; sin partidas fantasma | PASSED |
| 3 | `test_borrador_editable_incluye_partidas_y_orden_de_trabajo` | `PATCH /draft` actualiza encabezado, OT y partidas solo en `DRAFT` | PASSED |
| 4 | `test_envio_crea_solicitud_y_paso_de_aprobacion` | `SUBMITTED` + `ApprovalRequest`/`ApprovalStep` en `PENDING` | PASSED |
| 5 | `test_reglas_de_segregacion_autoautorizacion_y_decision_duplicada` | Autoautorización `403`; partida duplicada y rol no aprobador rechazados | PASSED |
| 6 | `test_rechazo_con_motivo_y_historial` | Rechazo sin motivo `422`; con motivo registra estado, timestamp y eventos consultables en `/history` | PASSED |
| 7 | `test_pending_qty_usa_autorizado_no_solicitado` | `pending_qty = authorised - delivered`, no `requested - delivered` | PASSED |
| 8 | `test_reserva_parcial_y_anti_sobrereserva` | Reserva parcial correcta; exceder autorizado o existencia → `409`; stock físico sin cambios | PASSED |
| 9 | `test_idempotencia_concurrente_reserva` | Dos hilos con la misma clave devuelven el mismo `StockReservation` | PASSED |
| 10 | `test_concurrencia_claves_distintas_no_sobrereserva` | Dos claves distintas por 8 und. sobre saldo 10 und.: una confirma y la otra falla `409` | PASSED |
| 11 | `test_cancelacion_libera_reservas_y_registra_auditoria` | Cancelación autorizada libera reservas, cancela partidas y escribe bitácora | PASSED |
| 12 | `test_linea_rechazada_queda_cancelada_y_no_se_puede_reservar` | Partida rechazada queda `CANCELLED` con `authorised_qty = 0`; intentar reservarla → `409` | PASSED |
| 13 | `test_expiracion_de_reserva_devuelve_saldo` | Reserva vencida pasa a `EXPIRED` y devuelve exactamente el remanente reservado | PASSED |
| 14 | `test_entrega_parcial_y_cierre_automatico` | Entrega de todas las partidas genera movimientos `ISSUE` y cierra la requisición | PASSED |
| 15 | `test_idempotencia_concurrente_entrega` | Dos hilos con la misma clave devuelven el mismo movimiento; no hay doble descuento | PASSED |
| 16 | `test_oc_cancelada_vuelve_a_contar_como_faltante` | Cancelar OC devuelve el faltante; `purchased_qty` excluye OC canceladas/cerradas | PASSED |
| 17 | `test_adjuntos_controlados_registran_sha256_y_rechazan_tipo` | PDF aceptado con SHA-256 y responsable; tipo no permitido → `422` | PASSED |
| 18 | `test_idempotencia_concurrente_creacion_oc` | Dos hilos con la misma clave devuelven la misma OC; No hay duplicado | PASSED |

## 4. Evidencia de base de datos

Salida real de `python -m alembic current` en `erp_minero_dev` y `erp_minero_test`:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
f4a7c1e2b3d6 (head)
```

Conteo real de tablas por esquema en ambas bases:

```text
aud 1   cost 2   doc 5   intg 3   inv 3   mdm 3
mnt 1   org 5    pur 4   req 3   seg 8   wfl 3
TOTAL 41
```

39 tablas provienen de la Fase 3; las 2 nuevas son `doc.idempotency_record` y `req.requisition_attachment`. No se eliminó ni recreó ninguna tabla. `downgrade()` está bloqueado por política.

## 5. Hallazgos detectados durante la verificación y correcciones aplicadas

1. **Modelo de adjuntos discrepante con la migración.** `RequisitionAttachment` heredaba `AuditMixin`, que agrega `created_by`, `updated_at`, `updated_by` y `version`; la migración aplicada solo crea `id` y `created_at`. El primer insert falló con `UndefinedColumn: no existe la columna «created_by» en la relación «requisition_attachment»`. Se alineó el modelo con la migración: se eliminó `AuditMixin`, se definieron `id` y `created_at` y se quitó `created_by=actor_id` en `RequisitionService.add_attachment()`.
2. **Helper de pruebas con atributo inexistente.** `Item` expone `description`, no `name`; el helper usaba `items[index].name`. Corregido, junto con una consulta muerta a `Supplier`.
3. **Prueba de rechazo no alcanzable.** La prueba original intentaba rechazar una requisición con una reserva previa, pero reservar exige estado `APPROVED`/`PARTIALLY_APPROVED`, incompatible con `SUBMITTED`. Se reformuló como «partida rechazada queda cancelada y no se puede reservar», que cubre la misma garantía en un camino real.
4. **Claves de idempotencia reutilizadas entre ejecuciones.** Las pruebas de concurrencia usaban claves fijas; en una segunda ejecución, `acquire()` devolvía las entidades confirmadas por la anterior y la comprobación de anti-sobrereserva parecía fallar. Instrumentando `line_reserved_qty` se confirmó que el bloqueo funciona (`0` para el primer hilo, `9.000000` para el segundo). Se cambiaron las claves por `uuid.uuid4()`.
5. **Contaminación entre pruebas por datos confirmados.** Las pruebas concurrentes hacen `commit()` en conexiones independientes; sus folios y saldos persistían y chocaban con las pruebas que revierten su transacción (`document_registry` duplicado y existencias cambiadas). Se agregó `reset_test_database()` en `tests/conftest.py` con un fixture `autouse` de sesión y un fixture por módulo en `test_phase4_requisiciones.py`. El reinicio usa `TRUNCATE ... RESTART IDENTITY CASCADE` **solo sobre `erp_minero_test`** y vuelve a sembrar datos sintéticos; nunca toca la base de desarrollo ni datos reales.
6. **Cierre automático sobrescribía partidas canceladas.** `_maybe_close_requisition` marcaba `CLOSED` todas las partidas. Se ajustó para omitir las que ya están `CANCELLED`, preservando el motivo de cancelación.
7. **Regresión de lint.** Tras las correcciones, `ruff` detectó un import `Requisition` sin usar en el archivo nuevo; se retiró. `ruff check .` quedó limpio.

## 6. Limitación de entorno: verificación `empty -> head`

Se intentó validar la cadena completa de migraciones creando una base temporal `erp_minero_f4_check` y ejecutando `alembic upgrade head` sobre ella. El usuario `erp_minero_app` no tiene permiso `CREATEDB`:

```text
psycopg.errors.InsufficientPrivilege: se ha denegado el permiso para crear la base de datos
```

No es un fallo funcional de la migración: la revisión `f4a7c1e2b3d6` está aplicada y el esquema resultante fue inspeccionado en las dos bases disponibles. El script temporal `backend/f4_migration_check.py` creado para el intento **fue retirado** y no forma parte del cambio; además contenía un `DROP DATABASE` sobre la base temporal que no debe versionarse. Para cerrar esta limitación se requiere un rol con `CREATEDB` o que un administrador cree la base vacía.

## 7. Estado de Git y secretos

- Commit previo de recuperación: `6a05492 Agrega identidad, sesiones y RBAC de la Fase 3`. **Sin push.**
- Commit local de la Fase 4: `git log -1` muestra el commit con 27 archivos (21 modificados y 6 nuevos). **Sin push.**
- `.gitignore` excluye `.env`, `.env.*`, `node_modules/`, `frontend/dist/` y, desde esta fase, `var/` (contenido de adjuntos).
- `git diff --check` no reporta errores de whitespace; solo avisos de normalización LF→CRLF de Git en Windows.
- Búsqueda en el diff con `password|secret|token|DATABASE_URL|erp_minero_app:` → **sin coincidencias**. Las credenciales se leen de `.env` (no versionado) y las contraseñas demo de `DEMO_PASSWORD`.
- No se agregaron datos reales: todas las entidades de prueba provienen de `seed_demo_data()` y sus nombres llevan prefijo `DEMO`.

## 8. Alcance no cubierto

- Triple match OC–recepción–factura: sigue pendiente y bloquea el uso en producción.
- Decisión parcial por partida en la bandeja de autorizaciones de la UI (disponible solo en la API).
- Verificación `empty -> head` con `CREATEDB` (§6).
- No se modificaron CONTPAQi, Sierra Madre GMAO ni sistemas de la mina; no se generaron archivos para ellos ni se publicaron asientos.
- No se hizo `git push`, tag ni despliegue.
