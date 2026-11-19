# Fase 3 — Usuarios, autenticación y RBAC: resultados

**Fecha:** 2026-11-18
**Ruta física:** `E:\ERP_MINERO`
**Estado:** IMPLEMENTADA Y VERIFICADA en PostgreSQL 17.12 real. Sin datos reales ni credenciales versionadas.
**Commit previo de recuperación:** `c78b124 Agrega base PostgreSQL, migraciones y pruebas de la Fase 2` (sin push).
**Alcance:** Fase 3 de identidad/sesiones/RBAC. **No** se desarrollaron los circuitos transaccionales completos de Requisiciones, Almacén ni Compras; esos dominios conservan su implementación de fases anteriores.

---

## 1. Resumen ejecutivo

- Autenticación con **Argon2id** (64 MiB, 3 iteraciones, 4 hilos), con verificación retrocompatible de hashes bcrypt y actualización automática tras el primer acceso.
- **Sesiones opacas**: token de 256 bits entregado solo en cookie `HttpOnly`; en PostgreSQL se guarda únicamente `SHA-256` del token. No existe token de sesión en `localStorage`.
- **CSRF**: cookie legible `erp_csrf` más cabecera `X-CSRF-Token`, exigida por el backend en `POST/PUT/PATCH/DELETE` cuando autentica la cookie. El Bearer heredado tiene precedencia para no romper integraciones ni pruebas anteriores.
- Bloqueo por intentos fallidos (5 intentos / 15 minutos), cuentas `ACTIVE/INACTIVE/LOCKED`, contraseñas temporales con cambio obligatorio y restablecimiento seguro por administrador.
- RBAC con **40 códigos**: 19 alias en español (incluidos los 11 exigidos), 6 códigos canónicos internos y 15 códigos heredados de la Fase 2. Denegación por defecto, múltiples roles por usuario y alcance por departamento/unidad minera.
- Reglas de negocio: prohibida autoautorización de requisiciones, prohibida auto-concesión de rol administrativo, baja lógica de usuarios (nunca borrado físico), bitácora inmutable por trigger de base de datos.
- Portal React: acceso profesional, menú por permisos, panel de usuarios, alta/edición, roles y departamentos, cambio de contraseña, acceso denegado y auditoría de solo lectura.
- **42 pruebas backend** (26 regresiones + 16 nuevas) y **7 pruebas frontend**, todas sobre PostgreSQL real y jsdom respectivamente.

## 2. Cambios en la base de datos

Migración aditiva `f3a9c1d7b2e4_fase3_identidad_seguridad` (revises `d147e7ec92fb`):

| Objeto | Cambio |
|---|---|
| `seg.app_user` | `failed_login_attempts`, `locked_until`, `must_change_password`, `password_changed_at/by`, `deactivated_at/by` + CHECK de intentos no negativos |
| `seg.user_session` | Nueva: hash de token, hash CSRF, expiración, revocación, hash de IP y de User-Agent |
| `seg.user_department` | Nueva: alcance por departamento con baja lógica (`revoked_at/by`) |
| `seg.login_audit` | `user_agent_hash`; los registros de fallo guardan motivo, nunca contraseñas |
| `aud.audit_log` | Trigger `trg_audit_log_immutable` que bloquea `UPDATE`/`DELETE` incluso para ADMIN desde la aplicación |

- No se recrearon las 37 tablas de la Fase 2 ni se modificó la migración base.
- No hay `DROP`, `TRUNCATE` ni `DELETE` masivo. `downgrade()` lanza `RuntimeError` por política del repositorio.
- Revisión verificada: `f3a9c1d7b2e4 (head)` en `erp_minero_dev` y `erp_minero_test`.
- Tablas base por esquema: `seg 8, org 5, mdm 3, doc 4, req 2, wfl 3, inv 3, pur 4, mnt 1, cost 2, intg 3, aud 1` = **39** (37 tablas de la Fase 2 + 2 nuevas de la Fase 3).

## 3. Backend

| Archivo | Cambio principal |
|---|---|
| `app/core/security.py` | Argon2id, verificación bcrypt transitoria, tokens opacos, hashes SHA-256, comparación constante |
| `app/core/cookies.py` | `erp_session` (HttpOnly) y `erp_csrf` (legible), SameSite/Secure configurables |
| `app/core/config.py` | `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_DOMAIN` con validación |
| `app/api/v1/deps.py` | Cookie + CSRF, precedencia Bearer, `require_permission` y `require_any_permission` con bloqueo de contraseña temporal |
| `app/api/v1/routers/auth.py` | `login`, `logout`, `/me`, `change-password`, listado y revocación de sesiones |
| `app/api/v1/routers/admin.py` | Altas, bajas lógicas, edición, roles, departamentos, restablecimiento, permisos y sesiones |
| `app/api/v1/routers/audit.py` | Bitácora de solo lectura con filtro por acción y límite |
| `app/api/v1/routers/requisitions.py` | Filtro por departamento en listado/detalle/creación y catálogos filtrados por alcance |
| `app/modules/requisitions/service.py` | Autoautorización rechazada con `403` antes de validar decisiones |
| `app/modules/purchasing/models.py`, `app/modules/requisitions/models.py` | Orden determinista de partidas (`order_by=line_no`) para que el orden de la API no dependa del orden físico de PostgreSQL; corrige 2 regresiones latentes detectadas al aislar las pruebas |
| `app/modules/identity/service.py` | Sesiones, intentos fallidos, RBAC, alcance, reglas anti-escalada y proyecciones sin secretos |
| `app/shared/constants.py` | Catálogo RBAC completo y `canonical_permission()` |
| `app/db/seed.py` | Roles/permisos en español, cuentas `demo.jefe`, `demo.gerencia`, `demo.auditor`, `demo.temporal` y departamentos `DEMO-MINA`, `DEMO-MANT`, `DEMO-OTRA`, unidad `LAG_OTRA_DEMO` |
| `pyproject.toml` | Dependencia `argon2-cffi>=23.1` |

> Nota de corrección aplicada: `DecisionRequest.decisions` permite cuerpo vacío en el esquema para que el servicio evalúe primero la autoautorización (403). La regla de "al menos una decisión" sigue vigente en el servicio para usuarios autorizados.

## 4. Frontend

| Archivo | Cambio |
|---|---|
| `src/api/client.ts` | `fetch` con `credentials: 'include'`, CSRF en escrituras, sin `Bearer` en memoria; endpoints de administración |
| `src/auth/AuthContext.tsx` | Sesión descubierta vía `/auth/me`, CSRF solo en memoria, logout en servidor, cambio de contraseña |
| `src/auth/permissions.ts` | Helper `can()` para ocultar menús (la autorización real sigue siendo del backend) |
| `src/App.tsx` | `RequireAuth`, `RequirePermission` y rutas `/usuarios`, `/auditoria`, `/cambiar-contraseña`, `/acceso-denegado` |
| `src/components/Layout.tsx` | Menú filtrado por permisos, roles legibles, aviso de contraseña temporal |
| `src/features/auth/Login.tsx` | Pantalla de acceso profesional con cuentas sintéticas sugeridas |
| `src/features/auth/ChangePassword.tsx` | Cambio de contraseña con confirmación y política visible |
| `src/features/auth/AccessDenied.tsx` | Pantalla de denegación con perfil actual |
| `src/features/admin/Users.tsx` | Alta/edición, roles, departamentos, restablecimiento y baja lógica |
| `src/features/audit/Audit.tsx` | Consulta de bitácora de solo lectura |
| `src/api/types.ts`, `src/styles.css`, `src/api/client.test.ts`, `src/App.test.tsx` | Tipos, estilos y pruebas |

## 5. Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
pytest -q
ruff check .
mypy app
python -m alembic current

cd E:\ERP_MINERO\frontend
npm.cmd run build
npm.cmd run test -- --run
```

| Verificación | Resultado |
|---|---|
| `pytest -q` | **42 passed** (26 regresiones + 16 pruebas nuevas Fase 3) |
| `ruff check .` | `All checks passed!` |
| `mypy app` | `Success: no issues found in 61 source files` |
| `python -m alembic current` | `f3a9c1d7b2e4 (head)` |
| `npm.cmd run build` | `tsc -b && vite build` correcto; 50 módulos transformados |
| `npm.cmd run test -- --run` | **7 passed** (2 archivos) |
| `git diff --check` | Sin errores (solo avisos LF→CRLF de Git en Windows) |
| `.gitignore` | `.env`, `.env.*` ignorados; salvo `!.env.example` |

Detalle de las 16 pruebas nuevas: ver `docs/EVIDENCIA_FASE3.md`.

## 6. Seguridad comprobada

- Ningún hash, token de sesión ni contraseña aparece en respuestas, bitácora ni pruebas.
- El restablecimiento genera la contraseña temporal en el servidor y la devuelve **una sola vez**; no se registra en `audit_log`.
- Las cookies usan `HttpOnly` para la sesión; `Secure` se activa con `SESSION_COOKIE_SECURE=true` bajo HTTPS.
- No hay tokens en `localStorage` (prueba frontend dedicada).
- `git diff --check` y la revisión de `.gitignore` confirman que no se versionan secretos.

## 7. Limitaciones y siguiente paso

- Los cambios de Fase 3 están **sin commitear**; no se hizo `git push` ni despliegue.
- No se conectó a CONTPAQi, Sierra Madre GMAO ni al servidor de la mina.
- El inventario del ERP sigue siendo operativo; CONTPAQi permanece como inventario oficial.
- La cookie `erp_session` requiere `SESSION_COOKIE_SECURE=true` cuando el portal se sirva por HTTPS en intranet; en local se mantiene `false` para `http://127.0.0.1`.
- Quedan fuera de esta fase las correcciones pendientes del informe `AUDITORIA_CODEX.md` relativas a circuitos transaccionales (idempotencia atómica, expiración de reservas, triple match, etc.).
- Siguiente paso recomendado: revisar y commitear Fase 3 localmente, y después atender los hallazgos CRÍTICOS/ALTOS de `docs/AUDITORIA_CODEX.md` con sus pruebas correspondientes.
