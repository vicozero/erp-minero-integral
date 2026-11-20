# Resultados — Lote 8: estabilización de almacenamiento, seguridad e integridad

**Fecha:** 20/11/2026  
**Repositorio:** `E:\ERP_MINERO`  
**HEAD sin cambios:** `8421472619a0c62f460b6d063e14a4f850186a72` (`8421472`)  
**Estado:** corregido tras reauditoría y revalidado localmente con datos sintéticos. **No se declara producción, no se hizo commit ni push.**  
**Alcance:** autenticación, sesiones, RBAC, inventario, autorización de compras, proxy local, precisión del informe y regresiones.

---

## 1. Resumen ejecutivo

| Área | Antes del Lote 8 | Después de la reauditoría |
|---|---|---|
| Respaldo de `erp_minero_dev` | Sin copia protectora verificada en este lote | `dump` validado con restauración aislada |
| Bearer y cookie | Bearer no se invalidaba al cerrar sesión; cookie sin versión de credencial | Ambos validan `sid` + versión; cookie con `credential_version` persistida |
| TOCTOU login/cambio de contraseña | Sesión podía crearse con credencial revocada | Bloqueo `FOR UPDATE` en `authenticate`, `change_password` y `reset_password` |
| Auditoría de autoaprobación denegada | Evento se registraba, pero la excepción impedía confirmarlo | `SelfApprovalDenied` + confirmación explícita en el router; prueba con `after_commit` |
| Detalle de saldos | CHECK invertido y sincronización incompatible con el backfill | CHECK corregido; reconciliación por `(warehouse_id, item_id)` |
| Alcance RBAC | Parcial; `WAREHOUSE`/`MINING_UNIT` sin validar al asignar | Alcance centralizado y validado también al asignar roles |
| Host/Origen y proxy | Validación incompleta; puerto `8000` fijo; fallos HTTP/1.1 | Host configurable, CORS con `Authorization`, proxy endurecido |
| `last_seen_at` | Se modificaba en la sesión inyectada y podía perderse | Escritura acotada en sesión propia con throttling |
| Migración `empty -> head` | `c3d4e5f6a7b8` | **`e4f5a6b7c8d9`**, aditiva y verificada |
| Pruebas backend | 148 línea base (141 versionadas + 7 sin seguimiento) | **175** (27 nuevas) |
| Pruebas frontend | 63 | **63** |
| Evidencia visual | 18 capturas previas al endurecimiento final | 18 capturas repetidas con el código final |

Se mantuvieron todas las pruebas existentes. No se relajaron controles ni se modificaron pruebas sólo para obtener verde. Las cinco aprobaciones de compra que usaban al creador como aprobador se ajustaron para usar un aprobador distinto, preservando la separación de funciones.

---

## 2. Reauditoría del informe: 20 hallazgos

La reauditoría del documento encontró 20 imprecisiones u omisiones. Estado al cierre:

| ID | Hallazgo | Estado |
|---|---|---|
| A1 | Auditoría de autoaprobación no persistida (alta) | **Corregido**: confirmación explícita y prueba real de commit |
| A2 | Servicios importan FastAPI; no hay capa de repositorios (media) | **Precisado**: arquitectura real es routers → servicios → SQLAlchemy; deuda documentada |
| A3 | CSRF no se valida con Bearer (media) | **Precisado**: CSRF aplica a la ruta de cookie; Bearer usa `Authorization` |
| A4 | Origen aceptado por whitelist CORS (media) | **Precisado**: mismo origen se valida por esquema/host/puerto; whitelist sólo para desarrollo cruzado |
| A5 | `X-Forwarded-*` confiaba en un Host fijo `8000` (alta) | **Corregido**: `TRUSTED_PROXY_HOSTS` configurable |
| A6 | Login no validado visualmente (media) | **Corregido**: solicitud real de login → HTTP 200 dentro de la captura final |
| B1 | «15 esquemas» incluía `information_schema` (media) | **Precisado**: 15 esquemas no `pg_*` = 14 de negocio + `information_schema` |
| B2 | «65 tablas» mezclaba tablas y vistas (media) | **Precisado**: 59 tablas base + 6 vistas |
| B3 | Línea base de 148 incluía 7 pruebas sin seguimiento (media) | **Precisado**: 141 versionadas + 7 preexistentes sin seguimiento + 27 nuevas |
| B4 | Espacio libre informado como instantánea fija (baja) | **Precisado**: cifras variables; no se recalculan en el cierre |
| B5 | Eventos de disco previos incompletos (baja) | **Precisado**: lista observada, no inventario exhaustivo |
| B6 | Extremo 06:21 sin evidencia (baja) | **Precisado**: se conserva como observación, no como prueba de integridad |
| C1 | Migración «aditiva» que sustituye un CHECK (media) | **Precisado**: `c3d4e5f6a7b8` no es estrictamente aditiva; no modifica datos |
| C2 | Guardia `ALLOW_DESTRUCTIVE_DOWNGRADE` en migraciones iniciales (alta) | **Precisado**: no se habilitó ni ejecutó; queda como superficie pendiente de retiro |
| C3 | `cred` con resolución de segundo (baja) | **Precisado**: la cookie ya no depende sólo del claim; usa columna persistida |
| C4 | Errores excluían el login inicial (baja) | **Corregido**: login HTTP 200 verificado en la validación final |
| D1 | Artefactos y PDF/PNG sin seguimiento (media) | **Precisado**: no se commitearon ni eliminaron |
| D2 | `ALLOWED_HOSTS` amplio (media) | **Precisado**: apto para local; debe reducirse en intranet |
| D3 | Auditoría de rechazo sin persistencia (alta) | **Corregido**: mismo que A1 |
| D4 | No conexión externa no verificable (baja) | **Precisado**: se reporta como afirmación operativa, no prueba absoluta |

---

## 3. Correcciones de código tras la reauditoría

| # | Severidad | Corrección | Regresión |
|---|---|---|---|
| 1 | Alta | `FOR UPDATE` sobre `seg.app_user` en `authenticate`, `change_password` y `reset_password`; la sesión guarda `credential_version` | `test_lote8_auth.py` |
| 2 | Alta | `SelfApprovalDenied` y `db.commit()` en la rama de rechazo de OC | `test_lote8_purchase_approval.py` |
| 3 | Alta | `_sync_balance_detail` busca por ámbito canónico y calcula `legacy - otros`, compatible con backfill y múltiples saldos | `test_lote8_stock_detail.py` |
| 4 | Media | `expire_reservations` filtra por `StockReservation.warehouse_id` y bloquea sólo la tabla de reservas | `test_lote8_stock_detail.py` |
| 5 | Media | `TRUSTED_PROXY_HOSTS` sustituye el Puerto `8000` hardcodeado | `test_lote8_auth.py` |
| 6 | Media | El proxy rechaza `Content-Length` + `Transfer-Encoding`, limita la respuesta y sincroniza el log | `test_lote8_portal_proxy.py` |
| 7 | Media | `assign_role` valida existencia y alcance para `WAREHOUSE`, `MINING_UNIT` y `DEPARTMENT` | `test_lote8_rbac_scope.py` |
| 8 | Baja | `last_seen_at` se persiste en sesión propia con throttle configurable de 60 s | `test_lote8_auth.py` |
| 9 | Baja | CORS permite la cabecera `Authorization` | `test_lote8_auth.py` |
| 10 | Baja | `HEAD` no emite `Content-Length` | `test_lote8_portal_proxy.py` |
| 11 | Baja | Lock compartido para el log del proxy | `test_lote8_portal_proxy.py` |
| 12 | Baja | Tope de tamaño para respuestas del backend en el proxy | `test_lote8_portal_proxy.py` |

### Migración aditiva nueva

`backend/migrations/versions/e4f5a6b7c8d9_sesion_credencial.py`:

- Añade `seg.user_session.credential_version` (`INTEGER`, nullable).
- Las filas heredadas quedan en `NULL` y se rechazan en la ruta de cookie (**fail closed**).
- No backfillea, no elimina datos y `downgrade()` lanza `RuntimeError`.

---

## 4. Estado de la unidad `E:` y protección de datos

`PGDATA` permanece en `E:\erp_pgdata`. Al diagnóstico:

| Elemento | Resultado observado |
|---|---|
| Sistema de archivos | NTFS (`Windows8_OS`) |
| `HealthStatus` | `Warning` |
| `OperationalStatus` | `Full Repair Needed` |
| Espacio libre / tamaño | Instantáneas variables; no se recalculan en este cierre |
| Eventos previos | `Disk 153`, `Ntfs 140`, `Ntfs 50`, `Ntfs 98` (lista observada, no exhaustiva) |
| PostgreSQL | `PANIC: no se pudo escribir archivo de registro ... Invalid argument` |
| Caídas observadas | 19/11 19:53 y 21:00; 20/11 06:18→06:21 (extremo sin evidencia adicional) |

`Repair-Volume -DriveLetter E -Scan` devolvió `NoErrorsFound`, pero se ejecutó con `ADMIN=False`; por sí solo **no confirma integridad**. No se ejecutó `CHKDSK /F`, reparación, formateo ni movimiento de `PGDATA`.

### Respaldo protector

- Archivo: `C:\Users\Dell\AppData\Local\Temp\opencode\erp_minero_dev_lote8_20261120.dump`
- SHA256 verificado en el diagnóstico: `D0CDF8EFE9B10F3D4DF61EE365C8E118C5DC4EFE27BC81E30A45A7EE311DAD19`
- Restauración aislada verificada en `127.0.0.1:55432`: 15 esquemas no `pg_*` (14 de negocio + `information_schema`), 59 tablas base y 6 vistas.
- El clúster temporal de restauración fue eliminado. La base `erp_minero_dev` no fue modificada.

**Riesgo abierto:** la unidad `E:` sigue en `Warning`/`Full Repair Needed`. Requiere ventana autorizada para respaldo formal, `chkdsk`/reparación y traslado de `PGDATA` a disco sano.

---

## 5. Autenticación, sesiones y autorizaciones

- `AccessTokenClaims`, `credential_version`, `create_access_token` y `decode_access_token` permanecen en `app/core/security.py`.
- El Bearer incluye `sub`, `sid`, `cred`, `iat`, `exp` y `typ=access`.
- `sid` identifica una fila real de `seg.user_session`.
- `cred` se deriva de `password_changed_at`; ahora la ruta de cookie también guarda y compara esa versión en base.
- El Host de confianza para `X-Forwarded-*` se configura con `TRUSTED_PROXY_HOSTS` (por defecto, el proxy local `127.0.0.1:8000`/`localhost:8000`).
- CSRF se valida en operaciones de escritura con cookie; el Bearer se autentica mediante `Authorization` y no depende de cookie.
- La autoaprobación de OC sigue denegada por defecto y el evento `PURCHASE_ORDER_SELF_APPROVAL_DENIED` queda confirmado.
- **Estado de `erp_minero_dev` al cierre:** no se migró ni se aplicó backfill. Sigue en `a2b3c4d5e6f7`, con 3 saldos agregados, 0 filas de detalle y 3 saldos sin conciliar. Ahora hay dos revisiones pendientes: `c3d4e5f6a7b8` y `e4f5a6b7c8d9`.

---

## 6. Verificaciones ejecutadas

| Verificación | Resultado final |
|---|---|
| `python -m ruff check app tests` | **All checks passed!** |
| `python -m mypy app --follow-imports=silent` | **Success: no issues found in 85 source files** |
| Suite backend completa en clúster PostgreSQL efímero | **175 passed** |
| `alembic upgrade head` desde vacío | **`e4f5a6b7c8d9`**; 15 esquemas no `pg_*`, 59 tablas base, 6 vistas, columna `credential_version` presente |
| `npx.cmd tsc --noEmit` | OK, sin salida |
| `npm.cmd run test -- --run` | **63 passed / 16 archivos** |
| `npm.cmd run build` | OK; avisos de chunk >500 kB (`OrbitControls` 842.92 kB, `index` 381.21 kB) |
| Captura visual repetida con el código final | **18/18** páginas, **18/18** con `/api/v1/auth/me` → 200, 0 desbordes, 0 errores |
| `git diff --check` | OK; sólo avisos de normalización LF/CRLF |
| Escaneo de secretos en el diff | 0 coincidencias reales |
| HEAD / commit / push | Sin cambios: `8421472619a0c62f460b6d063e14a4f850186a72` |

El servicio local `postgresql-x64-17` está `Stopped` y `Start-Service` devolvió `No se puede abrir el servicio ... en el equipo '.'`. Por eso la suite completa y la verificación `empty -> head` se ejecutaron en clústeres PostgreSQL 17 efímeros, en `127.0.0.1`, con codificación UTF8, rol no superusuario y datos sintéticos. Los clústeres se detuvieron y eliminaron.

Las 27 pruebas nuevas se distribuyen así: 17 de autenticación/sesión/Host/Origen/CORS, 5 de alcance RBAC, 3 de detalle de inventario, 1 de separación de funciones en compras y 1 del proxy HTTP/1.1.

El escaneo de archivos modificados y nuevos sólo encontró dos coincidencias de patrón benignas: el marcador `<password>` en `.env.example` y una contraseña sintética en `backend/tests/test_lote8_auth.py`. No hay credenciales reales en el diff.

---

## 7. Validación visual con navegador real

Se usó **Chrome + CDP** con `Emulation.setDeviceMetricsOverride`. Las capturas son PNG reales, no maquetas.

| Resolución solicitada | Viewport medido | DPR | Capturas |
|---|---|---:|---:|
| 1920×1080 | 1920×1080 | 1 | 6 |
| 1366×768 | 1366×768 | 1 | 6 |
| 1280×720 | 1280×720 | 1 | 6 |

Se capturaron seis rutas por resolución: `/login`, `/`, `/requisiciones`, `/almacen`, `/compras` y `/ubicaciones`. El archivo `/login` se captura como ruta de entrada; con sesión activa la aplicación redirige al panel. La autenticación de login se validó con una solicitud `POST /api/v1/auth/login` real → HTTP 200, no con una captura aislada de la pantalla de acceso.

`docs/evidencia_lote8/evidencia.json` fue regenerado con el código final: 18 páginas con contenido real, 18 respuestas de sesión en 200, 0 desbordes horizontales y 0 errores de consola/red/HTTP ≥400. La validación usó datos sintéticos; API y portal escucharon sólo en `127.0.0.1:8000` y `127.0.0.1:8080`. No quedaron escuchas activas de esos servicios.

---

## 8. Arquitectura y seguridad verificadas

- La arquitectura real es routers → servicios → SQLAlchemy. **No se introdujo una capa de repositorios**; se documenta como desviación pendiente frente a `AGENTS.md`.
- Movimientos y hechos contables/de inventario siguen siendo `append-only`.
- Auditoría y eventos de documento se insertan en la misma transacción que el cambio de negocio; la excepción de autoaprobación confirma por separado sólo el evento de rechazo.
- Cabeceras de seguridad, cookie HttpOnly, hash de token en base y validación de sesión permanecen activas.
- Host/Origin se validan completos, incluido puerto; el proxy local es el único que puede aportar `X-Forwarded-Host`/`X-Forwarded-Proto`, según `TRUSTED_PROXY_HOSTS`.
- No se conectó a CONTPAQi ni Sierra Madre GMAO; no se accedió a producción ni se expusieron puertos a LAN. Esta afirmación es operativa, no una prueba absoluta desde el repositorio.
- No se imprimieron ni rotaron credenciales.
- Los artefactos PNG/PDF en la raíz, `docs/plantillas_referencia/**`, `var/secrets/` y `.env` no se versionaron. `frontend/tsconfig.tsbuildinfo` se dejó de rastrear y se ignoró; la evidencia sintética de `docs/evidencia_lote8/` sí se versionó.

---

## 9. Riesgos abiertos y siguiente paso

| Prioridad | Riesgo | Acción pendiente |
|---|---|---|
| 1 | `E:` en `Warning`/`Full Repair Needed` con `PGDATA` encima | Autorizar ventana: respaldo formal, `chkdsk`/reparación y traslado a disco sano |
| 2 | `erp_minero_dev` en `a2b3c4d5e6f7`, sin detalle y con 3 saldos sin conciliar | Decir sí/no al backfill controlado y aplicar `c3d4e5f6a7b8` + `e4f5a6b7c8d9` en ventana autorizada |
| 3 | Credencial de desarrollo local no rotada | Definir mecanismo de arranque y rotarla con autorización |
| 4 | Matriz de aprobadores de OC no formalizada | Decidir roles, montos y excepciones; sólo entonces retirar el modo conservador |
| 5 | Política de aprobadores de requisiciones con `ADMIN`/`SUPERADMIN` | Confirmar si deben aprobar o limitar a `APROBADOR`/`JEFE_DEPARTAMENTO` |
| 6 | Capa de repositorios ausente y guardias de downgrade heredadas | Decidir refactor y retiro de `ALLOW_DESTRUCTIVE_DOWNGRADE` en migraciones iniciales |
| 7 | Chunk `OrbitControls` de 842.92 kB y `index` de 381.21 kB | Evaluar `manualChunks` y carga diferida de Three.js |
| 8 | UX/accesibilidad y textos obsoletos pendientes del audit previo | Temas persistentes, modal de motivo, foco en modales y textos QR/SLA |
| 9 | `pytest` sin `--basetemp` falla por permisos del directorio temporal | Limpiar permisos de `pytest-of-Dell` en el entorno local |

**Siguiente paso recomendado:** no promover a producción. Primero resolver el riesgo de almacenamiento, la decisión de backfill y la aplicación controlada de las dos revisiones pendientes; después revisar aprobaciones, arquitectura y rotación de credenciales con autorización formal. El desglose por fases y sus puertas de autorización están en `docs/PLAN_DESPLIEGUE_LOTE8.md`.

---

## 10. Conclusión

La reauditoría encontró defectos altos reales; todos los hallazgos de código fueron corregidos o precisados, y el informe quedó ajustado a la evidencia verificable. La suite backend (175), la suite frontend (63), el tipo-check, el build, la migración `empty -> head` y la captura visual final pasaron con el código corregido.

**No se declaró terminada la puesta en producción.** Quedan abiertos y reportados la integridad física de `E:`, la migración/backfill de `erp_minero_dev`, la rotación de credenciales, la capa de repositorios y las decisiones empresariales de aprobación. No hay commit ni push; HEAD permanece en `8421472619a0c62f460b6d063e14a4f850186a72`.
