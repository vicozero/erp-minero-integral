# Auditoría integral — ERP MINERO INTEGRAL

**Fecha:** 2026-11-20  
**Repositorio:** `E:\ERP_MINERO`  
**HEAD auditado:** `8421472619a0c62f460b6d063e14a4f850186a72` (`8421472 Agrega diseñador profesional de planos 2D/3D para almacén virtual`)  
**Alcance:** código backend/frontend, migraciones Alembic, PostgreSQL local, seguridad, WMS 2D/3D, inventario operativo, documentos, SLA y navegador.  
**Estado:** auditoría y correcciones locales para revisión. **No se hizo commit ni push.** No se desplegó, no se exponen puertos y no se conectó a CONTPAQi ni Sierra Madre GMAO.

> Convención usada: **CRÍTICO** = riesgo de pérdida/indisponibilidad inmediata; **ALTO** = controle de seguridad o integridad que puede violarse; **MEDIO** = defecto funcional relevante con alternativa temporal; **BAJO** = calidad, UX o deuda técnica.  
> Toda fila marcada **Inspección** significa revisión de código/configuración. Toda fila marcada **Prueba** significa ejecución local con resultado registrado.

---

## A. Resumen ejecutivo

1. La línea base estaba limpia y verde: `ruff`, `mypy`, 141 pruebas backend, `tsc --noEmit`, 58 pruebas frontend y `vite build`.
2. Se aplicaron **8 correcciones verificables** con regresiones nuevas; el backend quedó en **148 pruebas** y el frontend en **63 pruebas**, ambos en verde.
3. El hallazgo más grave no está en el código sino en la infraestructura: `PGDATA` está en `E:\erp_pgdata`, la unidad `E:` reporta `HealthStatus=Warning` y `OperationalStatus=Full Repair Needed`, con errores NTFS/WAL previos. Requiere respaldo, ventana de mantenimiento y autorización; **no se reparó ni movió**.
4. Persisten riesgos de seguridad que requieren decisión: credencial de desarrollo expuesta localmente, JWT Bearer no invalidado al cerrar sesión/cambiar contraseña, alcance RBAC no aplicado de forma uniforme y autoaprobación de órdenes de compra.
5. El WMS 2D/3D quedó funcional en navegador y con defensas nuevas: ubicaciones por almacén, permisos reales de publicación/creación de ubicaciones, IDs estables de racks, validación de capacidad/altura, fallback 2D y liberación del contexto WebGL de prueba.
6. El inventario no se alteró: no se cargaron saldos reales, no se modificó el inventario oficial de CONTPAQi y las pruebas usaron únicamente datos sintéticos.
7. Los archivos PNG/PDF sin seguimiento y `docs/plantillas_referencia/` pertenecen al usuario y **no fueron tocados**.

### Conteo de hallazgos

| Estado | CRÍTICO | ALTO | MEDIO | BAJO | Total |
|---|---:|---:|---:|---:|---:|
| Abiertos / requieren decisión | 1 | 4 | 3 | 6 | 14 |
| Corregidos y verificados | 0 | 3 | 4 | 1 | 8 |

---

## B. Hallazgos

### B.1 Abiertos

| ID | Severidad | Tipo | Ubicación / evidencia | Riesgo | Acción propuesta |
|---|---|---|---|---|---|
| H-01 | **CRÍTICO** | Inspección + evidencia de sistema | `PGDATA=E:\erp_pgdata`; `Get-Volume E`: `Warning` / `Full Repair Needed`. Logs: `disk 153`, `Ntfs 140/50/98` y `PANIC: no se pudo escribir archivo de registro ... Invalid argument`. Caídas: 19/11 19:53 y 21:00; 20/11 06:18→06:21. | Caída repetida de PostgreSQL y posible pérdida de WAL/datos. | Respaldo verificado, `chkdsk` y migración de `PGDATA` a disco sano en ventana autorizada. **No ejecutado.** |
| H-02 | **ALTO** | Inspección | `var/secrets/admin_dev_credential.txt` existe, está ignorado por Git y no se imprimió su contenido. | Credencial de desarrollo expuesta localmente; si se reutiliza fuera de desarrollo, facilita acceso no autorizado. | Rotar credencial, retirar el archivo y documentar el nuevo mecanismo de arranque. **No rotado; requiere autorización.** |
| H-03 | **ALTO** | Inspección | `backend/app/core/security.py:80-105`; `backend/app/api/v1/deps.py:56-64`; `backend/app/modules/identity/service.py:227-232`. | El JWT Bearer de compatibilidad contiene `sub/iat/exp/typ`, sin `jti` ni liga a sesión. `logout` y `revoke_all_sessions` revocan filas de `UserSession`, pero el Bearer sigue válido hasta `exp`. | Incluir `jti`/`sid` en el token y verificarlo contra la sesión activa, o mantener Bearer sólo para integraciones con rotación controlada. **No ejecutado.** |
| H-04 | **ALTO** | Inspección | `backend/app/api/v1/deps.py:81-98` valida sólo el código de permiso. `backend/app/api/v1/routers/inventory.py:31,42,53,65,78,89` y `purchasing.py:31,41,50,62,74,86` no pasan alcance al servicio. | Un usuario con permiso global o con alcance asignado podría operar sobre almacén/departamento fuera de su alcance en inventario y compras. WMS/catálogos/requisiciones/documentos/SLA sí aplican alcance manualmente. | Generalizar una dependencia de alcance y aplicarla en inventario/compras. **No ejecutado.** |
| H-05 | **ALTO** | Inspección + prueba existente | `backend/app/modules/purchasing/service.py:172-193` no compara `actor_id` con el creador de la OC. `backend/tests/test_purchases.py:203-205` aprueba la OC con el mismo comprador que la creó. | Autoaprobación de órdenes de compra; rompe segregación de funciones. | Impedir `actor_id == created_by` y ajustar la prueba. **Revertido/quedó pendiente de decisión** porque la suite actual depende de ese comportamiento. |
| H-06 | **MEDIO** | Inspección | `backend/app/main.py:50-65` compara `request.url.hostname` y `urlsplit(origin).hostname` contra `ALLOWED_HOSTS`; ignora esquema y puerto. | Un `Origin` con el mismo hostname pero otro esquema/puerto pasa el middleware. CORS mitiga en navegador, pero la defensa de middleware es más débil. | Comparar contra la lista completa de orígenes permitidos (`CORS_ALLOW_ORIGINS`) y normalizar esquema/host/puerto. **No ejecutado.** |
| H-07 | **MEDIO** | Inspección + consulta SQL | `backend/migrations/versions/b7c8d9e0f1a2_lote_b_movimientos_wms.py:399-459` crea triggers de reconciliación sobre `inv.stock_balance_detail`. `Get-ChildItem backend/app ... 'stock_balance_detail'` no devuelve escrituras de la aplicación. Consulta actual: `stock_sin_detalle=3`. | La vista/trigger de conciliación no refleja el flujo real; los saldos heredados quedan fuera de la validación. | Backfill controlado y escritura de detalle desde el servicio de inventario, o ajustar el trigger a la realidad del modelo. **No ejecutado.** |
| H-08 | **MEDIO** | Inspección | `backend/app/shared/constants.py:366-368` incluye `SUPERADMIN` y `ADMIN` en `APPROVER_ROLE_CODES`; `backend/app/modules/requisitions/service.py:362-368`bloquea autoaprobación y exige rol aprobador, pero admite administradores. | Política de aprobación no formalizada: un administrador puede aprobar requisiciones ajenas. Puede ser correcto, pero debe decidirse. | Confirmar si `ADMIN`/`SUPERADMIN` deben aprobar o limitar a `APROBADOR`/`JEFE_DEPARTAMENTO`. **Pendiente de decisión.** |
| H-09 | **BAJO** | Inspección | `frontend/src/components/Layout.tsx:77,95-98` inicializa el tema desde `dataset.theme` y no lo persiste; `Designer.tsx:587` cambia tema local del diseñador. | El usuario pierde la preferencia de tema al recargar. | Persistir tema con clave no sensible, respetando la regla de no guardar tokens en `localStorage`. **No ejecutado.** |
| H-10 | **BAJO** | Inspección | `frontend/src/features/purchases/Purchases.tsx:91-99` usa `window.prompt` para el motivo de cancelación y valida `if (!reason)`. El backend sí exige `min_length=4` en `purchasing/schemas.py:43`. | UX inconsistente y ventanas nativas poco accesibles; el rechazo real ocurre en el servidor. | Sustituir por campo validado en modal. **No ejecutado.** |
| H-11 | **BAJO** | Inspección | `frontend/src/features/wms/Locations.tsx:396-397` dice que la lectura/impresión gráfica de QR está pendiente de Fase 5, mientras `VirtualMap.tsx:282-286` ofrece `Ver código QR` y existe `/qr.svg`. `Dashboard.tsx:245` dice que no existe política SLA en backend aunque hay endpoints `/api/v1/sla/...`. | Textos obsoletos que reducen confianza del usuario. | Actualizar textos a: token/SVG disponible y SLA calculado por política configurable. **No ejecutado.** |
| H-12 | **BAJO** | Inspección | Modales con `role="dialog"`/`aria-modal` en `components/ui.tsx:241`, `Requisitions.tsx:909`, `designer/Designer.tsx:566,815,828`, pero sin foco inicial atrapado ni cierre por `Escape` documentado. | Navegación por teclado y lectores de pantalla incompleta. | Implementar focus trap, foco inicial y `Escape`. **No ejecutado.** |
| H-13 | **BAJO** | Prueba | `vite build` termina correctamente pero advierte `OrbitControls` de `842.92 kB` y `index` de `381.21 kB` antes de gzip. | Carga inicial pesada en equipos de planta. | Evaluar `manualChunks` y carga diferida de Three.js. **No ejecutado.** |
| H-14 | **BAJO** | Prueba | `python -m pytest -q` sin `--basetemp` falla por `PermissionError: [WinError 5]` en `C:\Users\Dell\AppData\Local\Temp\pytest-of-Dell`. Con `--basetemp=...\pytest_auditoria` pasa. | Bloqueo del comando estándar en este entorno, no defecto de la aplicación. | Limpiar/otorgar permisos al directorio temporal de pytest del usuario. **Workaround aplicado y documentado.** |

### B.2 Corregidos y verificados

| ID | Severidad original | Corrección | Evidencia |
|---|---|---|---|
| C-01 | MEDIO | `alembic downgrade` bloqueado salvo `ALLOW_DESTRUCTIVE_DOWNGRADE=1`. | `backend/migrations/versions/d147e7ec92fb_tablas_iniciales_por_dominio.py:816-820`; prueba `test_downgrade_de_migracion_exige_autorizacion`. |
| C-02 | ALTO | Un administrador común ya no puede restablecer la contraseña de un SUPERADMIN. | `backend/app/modules/identity/service.py:738-745`; prueba con roles simulados vía `monkeypatch`. |
| C-03 | ALTO | WMS: ubicaciones referenciadas deben pertenecer al almacén; publicación devuelve permisos reales; racks con ID único, capacidad y altura validadas; errores de esquema convertidos en 422. | `wms_designer_service.py:61-75,308,358,482-504,623-639`; `routers/wms_designer.py:116-117`; 4 pruebas nuevas. |
| C-04 | ALTO | La entrega valida existencia y reserva **antes** de mutar saldos. | `backend/app/modules/inventory/service.py:387-393`; cubierto además por `tests/test_inventory.py::test_sobreentrega_bloqueada`. |
| C-05 | MEDIO | Reimpresión sin archivo original devuelve `409`, no regenera bytes. | `backend/app/modules/documentation/service.py:605-636`; prueba `test_reimpresion_sin_archivo_original_no_regenera_bytes`. |
| C-06 | MEDIO | Clave de idempotencia de vales estable por requisición + fecha. | `frontend/src/features/vouchers/Vouchers.tsx:22-24,109`; aserción en `Vouchers.test.tsx`. |
| C-07 | MEDIO | Evento central `401` y cierre de sesión en el cliente. | `frontend/src/api/client.ts:72,141-151`; `AuthContext.tsx:36-46`; prueba en `client.test.ts`. |
| C-08 | BAJO | Permisos correctos de ubicaciones/racks, `SceneErrorBoundary` en el diseñador, `onSaved` tras crear rack, liberación del contexto WebGL y clases CSS faltantes. | `WarehouseInteractive.tsx:50,560`; `RackWizard.tsx:30,38-44,68`; `Designer.tsx:5,400,750-763`; `webgl.ts:5-14`; `styles.css:238,249-250`. |

---

## C. Correcciones aplicadas

### C.1 Backend

1. **Migración destructiva protegida**  
   `backend/migrations/versions/d147e7ec92fb_tablas_iniciales_por_dominio.py:816-820`  
   `downgrade()` lanza `RuntimeError` salvo que exista `ALLOW_DESTRUCTIVE_DOWNGRADE=1`. No se ejecutó ningún downgrade.

2. **Protección de SUPERADMIN**  
   `backend/app/modules/identity/service.py:738-745`  
   `reset_password()` exige que el actor también tenga rol `SUPERADMIN` cuando el objetivo lo es.

3. **WMS designer**  
   - `wms_designer_service.py:61-75`: nueva validación `_assert_location_ids_in_warehouse`.
   - `:308` y `:358`: se aplica al guardar borrador y al publicar.
   - `:336-342,449`: `publish` acepta `can_edit`/`can_publish` reales.
   - `routers/wms_designer.py:116-117`: el router pasa los permisos calculados.
   - `:482-486`: sufijo UUID corto al slug del rack para evitar IDs duplicados.
   - `:500-504`: capacidad validada > 0 y altura acumulada dentro del lienzo.
   - `:623-639`: `ValidationError` de Pydantic se traduce a error HTTP controlado.

4. **Inventario**  
   `backend/app/modules/inventory/service.py:387-393`  
   Las comprobaciones `on_hand - quantity >= 0` y `reserved - quantity >= 0` ocurren antes de descontar. Se eliminaron las comprobaciones posteriores a la mutación.

5. **Documentos**  
   `backend/app/modules/documentation/service.py:605-636`  
   Si `DOCUMENT_STORAGE_DIR/<storage_name>` no existe, se devuelve `409` con mensaje accionable; no se calcula un PDF/XLSX sustituto.

### C.2 Frontend

1. **Vales** — `Vouchers.tsx:22-24,109`: `vale:<requisition_id>:<issue_date>`. Un reintento de la misma intención ya no crea otro vale.
2. **Sesión** — `client.ts:72,141-151` emite `erp:unauthorized` en 401, excepto en login/cambio de contraseña; `AuthContext.tsx:36-46` limpia CSRF/usuario y redirige a `/login`.
3. **WMS** — `WarehouseInteractive.tsx:50,560` usa `MANAGE_LOCATIONS` para crear ubicaciones, separado de `MANAGE_MAPS`; `RackWizard.tsx` desactiva `create_locations` sin ese permiso y lo fuerza a `false` al enviar.
4. **3D** — `webgl.ts:5-14` libera el contexto de prueba con `WEBGL_lose_context` cuando existe; `Designer.tsx:750-763` añade `SceneErrorBoundary` con regreso a 2D.
5. **Diseñador** — `Designer.tsx:400` llama a `onSaved()` tras crear un rack para recargar el workspace.
6. **Estilos** — `styles.css:238,249-250` agrega `.form-grid` y `.action-cell`, usados por vales, SLA y trazabilidad.

### C.3 Regresiones nuevas

- `backend/tests/test_auditoria_regresiones.py` — 7 pruebas:
  1. `test_downgrade_de_migracion_exige_autorizacion`
  2. `test_admin_comun_no_puede_restablecer_superadministrador`
  3. `test_plano_rechaza_ubicacion_wms_de_otro_almacen`
  4. `test_asistente_rack_valida_capacidad_y_altura_acumulada`
  5. `test_slugs_que_colisionan_no_duplican_ids_de_escena`
  6. `test_publicacion_devuelve_permisos_reales_del_actor`
  7. `test_reimpresion_sin_archivo_original_no_regenera_bytes`
- `frontend/src/api/client.test.ts` — nota 401 central.
- `frontend/src/features/vouchers/Vouchers.test.tsx` — clave de idempotencia estable.
- `frontend/src/features/wms/designer/RackWizard.test.tsx` — 2 pruebas de permiso de ubicaciones.
- `frontend/src/features/wms/webgl.test.ts` — 2 pruebas de detección/liberación de WebGL.

---

## D. Pruebas ejecutadas

| Verificación | Línea base | Estado final | Resultado |
|---|---|---|---|
| `python -m ruff check app tests` | OK | OK | `All checks passed!` |
| `python -m mypy app --follow-imports=silent` | OK, 85 archivos | OK, 85 archivos | `Success: no issues found in 85 source files` |
| `python -m pytest -q --tb=short --basetemp=...\pytest_auditoria` | 141 passed | **148 passed** | Sin fallos; advertencias de deprecación de Starlette/HTTP 422, no funcionales |
| `python -m pytest -q` sin `--basetemp` | — | Fallo de entorno | `PermissionError [WinError 5]` en `pytest-of-Dell`; ver H-14 |
| `node node_modules/typescript/bin/tsc --noEmit` | OK | OK | Sin salida |
| `node node_modules/vitest/vitest.mjs run` | 58/58 | **63/63**, 16 archivos | Todos los archivos en verde |
| `node node_modules/vite/bin/vite.js build` | OK | OK | `✓ built in 17.27s`; advertencia de tamaño de chunk (H-13) |

**Comando backend reproducible usado:**

```powershell
python -m pytest -q --tb=short --basetemp=C:\Users\Dell\AppData\Local\Temp\opencode\pytest_auditoria
```

**Nota:** las pruebas se ejecutan contra la base sintética `erp_minero_test`; no se modificó `erp_minero_dev` ni saldos reales.

---

## E. PostgreSQL

### E.1 Estado actual

| Elemento | Resultado |
|---|---|
| Servicio | `postgresql-x64-17`: `Running`, `StartType=Automatic` |
| Escucha | `127.0.0.1:5432` y `::1:5432`; sin exposición LAN |
| Versión | PostgreSQL 17.12 |
| `PGDATA` | `E:\erp_pgdata` |
| Unidad `E:` | `HealthStatus=Warning`, `OperationalStatus=Full Repair Needed`, NTFS |
| Alembic | `a2b3c4d5e6f7` en `erp_minero_dev` y `erp_minero_test` |
| Esquemas | 14: `aud,cost,doc,intg,inv,mdm,mnt,org,public,pur,req,seg,wfl,wms` |
| Tablas / vistas | 59 tablas base / 6 vistas |
| Duplicados de folios de negocio | 0 en `req.requisition`, `pur.purchase_order`, `pur.goods_receipt`, `doc.warehouse_voucher` |
| Duplicados de idempotencia | 0 en `doc.idempotency_record`, `inv.stock_movement`, `inv.stock_reservation`, `pur.goods_receipt`, `doc.warehouse_voucher` |
| Saldos sin detalle | `stock_sin_detalle=3` en cada base (heredados, ver H-07) |

### E.2 Caídas y causa probable

- 19/11 a las 19:53 y 21:00; 20/11 de 06:18 a 06:21.
- Eventos Windows: `disk 153`, `Ntfs 140/50/98`.
- Log PostgreSQL: `PANIC: no se pudo escribir archivo de registro ... Invalid argument`.
- No hay evidencia de detención manual, conflicto de puerto ni OOM.
- Conclusión: fallo de almacenamiento/NTFS en la unidad que contiene `PGDATA`. No se afirmó una causa física más específica ni se ejecutó reparación.
- Queda confirmar si la “segunda detención del 20/11” reportada por el usuario corresponde a otro evento distinto del intervalo 06:18→06:21.

### E.3 Datos de `doc.document_render`

La consulta de duplicados mostró:

- `REQ-LAG-2026-000003 / PDF / is_reprint=false`: 2 filas.
- `VA-000166 / PDF / is_reprint=false`: 4 filas.
- `VA-000166 / XLSX / is_reprint=false`: 3 filas.

No son folios oficiales duplicados: pertenecen al historial de renderizados. Sí merece decisión si cada descarga debe crear una fila nueva con `is_reprint=false` o reutilizar el original. No se borró ni modificó ninguna fila.

---

## F. Seguridad

### F.1 Controles verificados como presentes

- Autenticación por cookie HttpOnly + CSRF para el portal; Bearer conservado para integraciones heredadas.
- `ALLOWED_HOSTS` y middleware de Host/Origen (con la limitación H-06).
- Cabeceras de seguridad: `nosniff`, `DENY`, `Referrer-Policy`, `Permissions-Policy`, `COOP`, `CORP` y CSP.
- Contraseñas hasheadas con librería reconocida; sesiones con hash de token en base, no token en claro.
- Bitácora de auditoría y eventos de documento en las operaciones sensibles revisadas.
- Guard adicional contra restablecimiento de SUPERADMIN por un administrador común.
- Bloqueo de downgrade destructivo.

### F.2 Riesgos abiertos

1. **H-02 credencial local:** no se imprimió ni copió al informe; no se rotó.
2. **H-03 JWT Bearer:** logout/cambio de contraseña revoca sesiones de base, pero no el token Bearer ya emitido.
3. **H-04 alcance RBAC:** la dependencia `require_permission` ignora `scope_type`/`scope_id`; inventario y compras no aplican filtro de alcance. Sí lo aplican catálogos, requisiciones, documentos, SLA y WMS.
4. **H-05 autoaprobación de OC:** no hay verificación de separación de funciones; la corrección se dejó pendiente porque la suite actual la usa como escenario válido.
5. **H-08 rol aprobador:** `ADMIN`/`SUPERADMIN` cuentan como aprobadores. Requiere confirmación de política, no se cambió unilateralmente.

### F.3 Medidas no tomadas deliberadamente

- No se rotaron secretos.
- No se eliminó `var/secrets/admin_dev_credential.txt`.
- No se expuso ningún servicio a `0.0.0.0`.
- No se conectó a CONTPAQi ni GMAO.
- No se copiaron datos reales de producción.

---

## G. Almacén virtual 2D/3D

### G.1 Navegador

Se cargaron y verificaron rutas reales en navegador local:

`/`, `/permisos`, `/requisiciones`, `/almacen`, `/almacen-virtual`, `/vales`, `/semaforo`, `/catalogo`, `/ubicaciones`, `/historial`, `/trazabilidad`, `/mi-cuenta`, `/compras`, `/auditoria`, `/usuarios`, `/roles`.

- Los `401` iniciales de `/api/v1/auth/me` antes del login son esperados.
- «Editar plano» apareció tras completar la carga en `/almacen-virtual`; su ausencia momentánea era un estado transitorio, no un defecto.
- El navegador disponible usó `1000×700`; **no existía herramienta de cambio de viewport**, por lo que no se verificaron 1920×1080, 1366×768 ni 1280×720.

### G.2 Correcciones y comportamiento observado

- El plano se presenta como **referencial/versionado**, no como levantamiento exacto.
- Las existencias y fichas WMS provienen de la API; el plano no altera inventario.
- «Crear/vincular ubicaciones WMS» ahora depende de `warehouse.location.manage` y no de `warehouse.map.manage`.
- Publicar un plano devuelve `can_edit`/`can_publish` conforme a los permisos reales del actor.
- Los racks generan IDs únicos; se validan capacidad y altura acumulada.
- Si la escena 3D falla, `SceneErrorBoundary` conserva la vista 2D y permite volver a ella.
- La detección de WebGL libera el contexto de prueba; esto resolvió el fallo previo de `WarehouseInteractive.test.tsx` por agotamiento de contextos en jsdom.

### G.3 Limitaciones

- No se verificó importación DXF/DWG: no hay archivo autorizado ni levantamiento físico.
- No se simuló consumo histórico ni se generaron firmas.
- Las capas, rotación y medidas están implementadas en 2D; la vista 3D es referencial y dependiente de WebGL/Three.js.

---

## H. Inventarios, documentos y SLA

### H.1 Inventario

- No se alteraron saldos reales ni se crearon movimientos de producción.
- La entrega valida reserva, autorización y no negatividad antes de mutar `stock_balance`.
- El flujo de sobreentrega sigue devolviendo `409` y conservando el saldo (`test_inventory.py:114-141`).
- Queda abierta la inconsistencia H-07 entre `stock_balance` y `stock_balance_detail`.

### H.2 Documentos

- Las claves de idempotencia de vales ahora son estables.
- La reimpresión ya no regenera bytes cuando falta el original: devuelve `409`.
- No se modificaron formatos PDF/XLSX aprobados ni plantillas de `docs/plantillas_referencia/`.
- No se agregaron grafías de firmas; los nombres se registran como texto, como antes.

### H.3 SLA

- El semáforo se calcula en backend y se muestra separado del estado documental.
- Se verificaron filtro e historial SLA en frontend y endpoints en backend.
- **No se sustituyeron horas de reloj por horas hábiles**: la política de plazos sigue siendo configurable y queda pendiente de decisión formal.
- Existen textos obsoletos listados en H-11.

---

## I. Pendientes y siguiente paso

1. **Infraestructura (H-01):** autorizar respaldo + `chkdsk`/reparación y traslado de `PGDATA` a disco sano. No ejecutar sin ventana de mantenimiento.
2. **Seguridad (H-02 a H-05):** decidir rotación de credencial, invalidación de Bearer, alcance RBAC en inventario/compras y separación de funciones en OC.
3. **Política (H-08):** confirmar roles aptos para aprobación de requisiciones.
4. **Conciliación (H-07):** decidir backfill de detalle o ajuste del trigger; no borrar filas heredadas.
5. **Datos de planta:** levantamiento físico, saldos reales autorizados, DXF/DWG y consumo histórico siguen fuera de alcance.
6. **UX/accesibilidad (H-09 a H-12):** temas persistentes, modal de motivo, foco en modales y textos QR/SLA.
7. **Verificación pendiente:** resoluciones 1920×1080, 1366×768 y 1280×720 cuando haya herramienta de viewport.
8. **Confirmedación pendiente:** segunda detención del 20/11 reportada por el usuario.

---

## J. Evidencias

### J.1 Comandos y resultados relevantes

```text
git rev-parse HEAD
8421472619a0c62f460b6d063e14a4f850186a72

python -m ruff check app tests
All checks passed!

python -m mypy app --follow-imports=silent
Success: no issues found in 85 source files

python -m pytest -q --tb=short --basetemp=...\pytest_auditoria
148 passed

node node_modules/typescript/bin/tsc --noEmit
(sin salida)

node node_modules/vitest/vitest.mjs run
Test Files 16 passed (16)
Tests 63 passed (63)

node node_modules/vite/bin/vite.js build
✓ built in 17.27s

Get-Service postgresql-x64-17
Running / Automatic

Get-NetTCPConnection -State Listen -LocalPort 5432
127.0.0.1:5432, ::1:5432

Get-Volume -DriveLetter E
HealthStatus=Warning, OperationalStatus=Full Repair Needed

Consulta SQL agregada
alembic=a2b3c4d5e6f7, esquemas=14, tablas=59, vistas=6, stock_sin_detalle=3
```

### J.2 Servidores temporales

Al cierre se verificó, excluyendo el propio proceso de chequeo, que **no quedaban servidores `http.server`, `uvicorn` ni `vite` activos**. Tampoco había puertos de servidores efímeros en escucha.

### J.3 Secretos

No se imprimieron contraseñas, tokens, cadenas de conexión completas ni contenido de `var/secrets/admin_dev_credential.txt`.

---

## K. Estado Git

**HEAD:** `8421472`  
**Commit/push:** ninguno. Todos los cambios quedan en el árbol de trabajo para revisión.

### Modificados

```text
backend/app/api/v1/routers/wms_designer.py
backend/app/modules/documentation/service.py
backend/app/modules/identity/service.py
backend/app/modules/inventory/service.py
backend/app/modules/inventory/wms_designer_service.py
backend/migrations/versions/d147e7ec92fb_tablas_iniciales_por_dominio.py
frontend/src/api/client.test.ts
frontend/src/api/client.ts
frontend/src/auth/AuthContext.tsx
frontend/src/features/vouchers/Vouchers.test.tsx
frontend/src/features/vouchers/Vouchers.tsx
frontend/src/features/wms/WarehouseInteractive.tsx
frontend/src/features/wms/designer/Designer.tsx
frontend/src/features/wms/designer/RackWizard.tsx
frontend/src/features/wms/webgl.ts
frontend/src/styles.css
```

### Nuevos de la auditoría

```text
backend/tests/test_auditoria_regresiones.py
frontend/src/features/wms/designer/RackWizard.test.tsx
frontend/src/features/wms/webgl.test.ts
docs/AUDITORIA_CODEX_ERP_MINERO.md
```

### Sin seguimiento preexistentes del usuario — no tocados

```text
46ee354f-920f-47af-a674-45d486c3bd2d.png
603227b9-0832-4a09-9cd5-53a6b84802d6.png
Requisicion_REQ-0006_JL-03_2026-11-13.pdf
VA-000162.pdf
ddcdf2de-4bae-4349-b98b-9385b32cfe22.png
de8a842f-bcbc-4acb-8d4a-b0611017ef60.png
docs/plantillas_referencia/**
```

`var/secrets/admin_dev_credential.txt` está ignorado por Git y no aparece en `git status`; su contenido no se incluyó en este informe.

---

## Cierre

La auditoría cumplió el alcance solicitado: se inspeccionó, se corrigió con evidencia y se probó localmente. **No se declara ambiente de producción, no se hizo commit/push y no se modificaron sistemas externos ni datos reales.** Los riesgos H-01 a H-08 siguen abiertos y requieren autorización o decisión de negocio antes de cualquier nueva acción.
