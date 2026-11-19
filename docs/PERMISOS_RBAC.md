# Catálogo de permisos y matriz RBAC

**Fecha:** 2026-11-19 (actualizado en Lote 5)
**Fuente de verdad:** `backend/app/shared/constants.py` (`PERMISSIONS`, `PERMISSION_ALIASES`, `ROLE_PERMISSIONS`).
**Principio:** denegación por defecto. El backend comprueba permisos en cada petición; el frontend solo oculta menús y no constituye una barrera de seguridad.

---

## 1. Cómo funcionan los códigos

El proyecto conserva los 15 códigos de la Fase 2 (inglés) para no romper contratos existentes y agrega alias en español. Los alias se resuelven al código canónico mediante `canonical_permission()`, de modo que una política escrita con `almacenes.surtir` y otra con `inventory.issue` se comprueban como la misma autorización.

Además existen códigos canónicos internos (`requisition.view_own`, `requisition.view_department`, `user.view`, `role.assign`, `department.view`, `session.view`) que no tenían equivalente heredado, y los bloques incorporados en WMS, módulo documental, semáforo SLA, almacén virtual y Lote 4.

**Total actual: 78 códigos canónicos y 46 alias**, según `backend/app/shared/constants.py`.

## 2. Los 11 permisos exigidos

| # | Permiso solicitado | Código canónico | Endpoint principal | Verificado por |
|---:|---|---|---|---|
| 1 | `requisiciones.crear` | `requisition.create` | `POST /api/v1/requisitions` | `requisitions.create` |
| 2 | `requisiciones.ver_propias` | `requisition.view_own` | `GET /api/v1/requisitions` (filtrado) | `IdentityService.assert_department_access` |
| 3 | `requisiciones.ver_departamento` | `requisition.view_department` | `GET /api/v1/requisitions` (alcance) | filtro por `department_ids` |
| 4 | `requisiciones.autorizar` | `requisition.approve` | `POST /api/v1/requisitions/{id}/decide` | `requisitions.decide` |
| 5 | `almacenes.consultar` | `inventory.availability.view` | `GET /api/v1/inventory/availability` | `inventory.*` |
| 6 | `almacenes.reservar` | `inventory.reserve` | `POST /api/v1/inventory/reservations` | `inventory.*` |
| 7 | `almacenes.surtir` | `inventory.issue` | `POST /api/v1/inventory/issues` | `inventory.*` |
| 8 | `compras.consultar` | `purchase.view` | `GET /api/v1/purchases` | `purchases.*` |
| 9 | `compras.crear` | `purchase.order.create` | `POST /api/v1/purchases/from-shortages` | `purchases.*` |
| 10 | `usuarios.administrar` | `admin.users.manage` | `GET/POST/PATCH/DELETE /api/v1/admin/users` | `admin.py` (`_ADMIN`) |
| 11 | `auditoria.consultar` | `audit.view` | `GET /api/v1/audit` | `audit.list_audit` |

## 3. Catálogo completo y alias

### Códigos heredados (Fase 2)

`admin.users.manage`, `audit.view`, `inventory.availability.view`, `inventory.issue`, `inventory.kardex.view`, `inventory.reserve`, `purchase.order.approve`, `purchase.order.create`, `purchase.receive`, `purchase.view`, `requisition.approve`, `requisition.create`, `requisition.history.view`, `requisition.submit`, `requisition.view`.

### Alias en español y su destino canónico

| Alias en español | Código canónico |
|---|---|
| `requisiciones.crear` | `requisition.create` |
| `requisiciones.ver_propias` | `requisition.view_own` |
| `requisiciones.ver_departamento` | `requisition.view_department` |
| `requisiciones.autorizar` | `requisition.approve` |
| `requisiciones.historial` | `requisition.history.view` |
| `almacenes.consultar` | `inventory.availability.view` |
| `almacenes.reservar` | `inventory.reserve` |
| `almacenes.surtir` | `inventory.issue` |
| `almacenes.kardex` | `inventory.kardex.view` |
| `compras.consultar` | `purchase.view` |
| `compras.crear` | `purchase.order.create` |
| `compras.autorizar` | `purchase.order.approve` |
| `compras.recibir` | `purchase.receive` |
| `usuarios.administrar` | `admin.users.manage` |
| `usuarios.consultar` | `user.view` |
| `roles.asignar` | `role.assign` |
| `departamentos.consultar` | `department.view` |
| `sesiones.consultar` | `session.view` |
| `auditoria.consultar` | `audit.view` |
| `documentos.generar` | `document.render` |
| `vales.crear` | `warehouse.voucher.create` |
| `vales.emitir` | `warehouse.voucher.issue` |
| `semaforo.consultar` | `sla.view` |
| `semaforo.configurar` | `sla.policy.configure` |
| `semaforo.aprobar` | `sla.policy.approve` |

## 4. Roles y matriz de permisos

Los roles `APROBADOR`, `ALMACENISTA` y `COMPRADOR` se mantienen como alias compatibles de `JEFE_DEPARTAMENTO`, `ALMACEN` y `COMPRAS` respectivamente. Un usuario puede tener **varios roles**: los permisos se unen (no se restan).

| Permiso | ADMIN | SOLICITANTE | JEFE_DEPARTAMENTO | ALMACÉN | COMPRAS | GERENCIA | AUDITOR |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `requisiciones.crear` | ✓ | ✓ | ✓ | — | — | — | — |
| `requisiciones.ver_propias` | ✓ | ✓ | ✓ | — | — | — | — |
| `requisiciones.ver_departamento` | ✓ | — | ✓ | ✓ | — | ✓ | ✓ |
| `requisiciones.autorizar` | ✓ | — | ✓ | — | — | — | — |
| `requisiciones.historial` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `almacenes.consultar` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `almacenes.reservar` | ✓ | — | — | ✓ | — | — | — |
| `almacenes.surtir` | ✓ | — | — | ✓ | — | — | — |
| `almacenes.kardex` | ✓ | — | — | ✓ | — | ✓ | ✓ |
| `compras.consultar` | ✓ | — | — | ✓ | ✓ | ✓ | ✓ |
| `compras.crear` | ✓ | — | — | — | ✓ | — | — |
| `compras.autorizar` | ✓ | — | — | — | ✓ | — | — |
| `compras.recibir` | ✓ | — | — | — | ✓ | — | — |
| `usuarios.administrar` | ✓ | — | — | — | — | — | — |
| `roles.asignar` | ✓ | — | — | — | — | — | — |
| `departamentos.consultar` | ✓ | — | ✓ | — | — | — | ✓ |
| `sesiones.consultar` | ✓ | — | — | — | — | ✓ | — |
| `auditoria.consultar` | ✓ | — | — | — | — | ✓ | ✓ |

Notas:

- **ADMIN** Posee los 40 códigos del catálogo; es el único rol con `usuarios.administrar`.
- **GERENCIA y AUDITOR** son de solo lectura; no pueden crear ni autorizar documentos.
- **JEFE_DEPARTAMENTO** hereda permisos de solicitante y aprobador, más consulta de departamentos.
- La fila «compras.consultar» de Almacén se otorga para consultar recepciones; no implica poder crear ni autorizar OC.

## 5. Alcance (scoping)

El permiso responde «qué puede hacer»; el alcance responde «sobre qué registros».

1. **Global:** ADMIN no requiere filas de alcance; ve todos los departamentos y registros.
2. **Por departamento:** `seg.user_department` contiene las filas permitidas (alta lógica mediante `revoked_at`). `IdentityService.department_ids()` devuelve el conjunto permitido y `assert_department_access()` bloquea accesos ajenos con `403`.
3. **Por unidad minera:** `Department.mining_unit_id` permite agrupar departamentos por unidad (`LAG_OTRA_DEMO` queda fuera del alcance de las cuentas demo de Mina/Mantenimiento).
4. **Por propiedad:** `requisition.view_own` restringe al creador; `requisition.view_department` amplía al departamento asignado.
5. **Ventana de sesión:** el JWT y la cookie caducan en `ACCESS_TOKEN_EXPIRE_MINUTES` (60 por defecto). Las sesiones pueden revocarse una a una.

En la semilla sintética, `demo.solicitante`, `demo.aprobador`, `demo.almacenista`, `demo.comprador`, `demo.jefe` y `demo.temporal` tienen alcance `DEMO-MINA` + `DEMO-MANT`; `demo.gerencia` y `demo.auditor` tienen además `DEMO-OTRA`; `demo.admin` es global.

## 6. Reglas de seguridad reforzadas

| Regla | Implementación | Prueba |
|---|---|---|
| Denegación por defecto | `require_permission()` lanza `403` si no hay coincidencia | `test_permisos_insuficientes_para_administrar` |
| Sin autoautorización | `RequisitionService.decide()` compara `actor_id` con `created_by_id` | `test_impide_autoautorizacion_de_requisicion` |
| Sin auto-concesión de ADMIN | `IdentityService.assign_role()` bloquea asignarse `ADMIN` a sí mismo | `test_impide_escalada_de_privilegios` |
| Auditoría inmutable | Trigger `trg_audit_log_immutable` en `aud.audit_log` | `test_cambios_sensibles_quedan_en_auditoria` |
| Sin secretos en bitácora | Fallos de login guardan `reason`, nunca contraseña ni hash | `test_contrasena_incorrecta_no_registra_secreto` |
| Baja lógica | `DELETE /admin/users/{id}` marca `INACTIVE`/`deactivated_at` | `test_usuario_inactivo_no_puede_entrar` |

## 7. Endpoints por módulo y permiso exigido

| Método | Ruta | Permiso |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Público (registra intento) |
| `POST` | `/api/v1/auth/logout` | Sesión activa + CSRF si autentica cookie |
| `GET` | `/api/v1/auth/me` | Sesión activa |
| `POST` | `/api/v1/auth/change-password` | Sesión activa + CSRF |
| `GET` | `/api/v1/auth/sessions` | Sesión activa |
| `POST` | `/api/v1/auth/sessions/{id}/revoke` | Sesión activa + CSRF |
| `GET/POST/PATCH/DELETE` | `/api/v1/admin/users...` | `usuarios.administrar` |
| `POST/DELETE` | `/api/v1/admin/users/{id}/roles...` | `roles.asignar` |
| `PUT` | `/api/v1/admin/users/{id}/departments` | `usuarios.administrar` |
| `POST` | `/api/v1/admin/users/{id}/reset-password` | `usuarios.administrar` |
| `GET` | `/api/v1/admin/roles` | `roles.asignar` |
| `GET` | `/api/v1/admin/permissions` | `usuarios.administrar` |
| `GET` | `/api/v1/admin/departments` | `departamentos.consultar` (filtrado si no ADMIN) |
| `GET` | `/api/v1/admin/sessions` | `sesiones.consultar` |
| `GET` | `/api/v1/audit` | `auditoria.consultar` (solo lectura) |
| `GET/POST` | `/api/v1/requisitions...` | `requisiciones.crear` / `ver_propias` / `ver_departamento` |
| `POST` | `/api/v1/requisitions/{id}/decide` | `requisiciones.autorizar` |
| `GET` | `/api/v1/inventory/availability` | `almacenes.consultar` |
| `POST` | `/api/v1/inventory/reservations` | `almacenes.reservar` |
| `POST` | `/api/v1/inventory/issues` | `almacenes.surtir` |
| `GET/POST` | `/api/v1/purchases...` | `compras.consultar` / `compras.crear` |

> Nota de compatibilidad: las rutas de dominio operativo conservan los códigos heredados en inglés en sus decoradores. Como los alias se normalizan con `canonical_permission()`, un rol con el permiso en español obtiene el mismo resultado. No se modificó la lógica transaccional de esos dominios en esta fase.

## 8. Cómo modificar permisos

1. Editar `backend/app/shared/constants.py`: agregar el alias a `PERMISSIONS_FASE3`, su mapeo en `PERMISSION_ALIASES` y, si aplica, el código a la tupla del rol en `ROLE_PERMISSIONS`.
2. La semilla `backend/app/db/seed.py` sincroniza la tabla `seg.permission` con `PERMISSIONS` en cada ejecución.
3. Agregar la prueba correspondiente en `backend/tests/test_phase3_auth_rbac.py`.
4. Ejecutar `pytest -q`, `ruff check .` y `mypy app`.
5. Actualizar este documento.

## 9. Permisos incorporados en el Lote 5

| Código canónico | Alias en español | Endpoint principal | Roles con acceso directo |
|---|---|---|---|
| `document.render` | `documentos.generar` | `GET /api/v1/documents/requisitions/{id}/pdf`, `GET /api/v1/documents/vouchers/{id}/pdf` | ADMIN, SUPERADMIN, SOLICITANTE, JEFE_DEPARTAMENTO, ALMACÉN, COMPRAS, GERENCIA, AUDITOR |
| `warehouse.voucher.create` | `vales.crear` | `POST /api/v1/documents/vouchers` | ADMIN, SUPERADMIN, ALMACÉN |
| `warehouse.voucher.issue` | `vales.emitir` | `POST /api/v1/documents/vouchers/{id}/issue`, `POST /api/v1/documents/vouchers/{id}/signatures` | ADMIN, SUPERADMIN, ALMACÉN |
| `sla.view` | `semaforo.consultar` | `GET /api/v1/sla/requisitions` | ADMIN, SUPERADMIN y todos los roles operativos/de lectura |
| `sla.policy.configure` | `semaforo.configurar` | servicios/migración de políticas SLA | ADMIN, SUPERADMIN |
| `sla.policy.approve` | `semaforo.aprobar` | aprobación de emergencia 4/8 h | ADMIN, SUPERADMIN |
| `requisition.history.view` | `requisiciones.historial` | `GET /api/v1/requisitions/{id}/trace` | ADMIN, SUPERADMIN y roles con historial |

Notas del Lote 5:

- El frontend usa `PERM.VIEW_VOUCHERS`, `PERM.VIEW_SLA` y `PERM.VIEW_TRACE` para mostrar menús y botones; la autoridad real la comprueba el backend en cada petición.
- `GET /api/v1/requisitions/{id}/trace` requiere `requisition.history.view`; un perfil sin ese permiso recibe `403` aunque vea el folio en el tablero.
- Las descargas y la reimpresión requieren `document.render` y aplican alcance por departamento.
- La emisión de un vale y el registro de nombres requieren `warehouse.voucher.issue`; no basta con poder generarlo.
- No se agregó ningún permiso nuevo en el Lote 5: los siete códigos canónicos de esta tabla ya existían y solo se documentaron sus alias y rutas.
