# Resultados — Lote 4: seguridad, credenciales y revisión local

Fecha: 19/11/2026. Estado: **validado localmente, solo para revisión visual en desarrollo**. No se declara apto para producción.

## 1. Autorización y alcance

Se ejecutó sobre la base de desarrollo `erp_minero_dev` con autorización explícita. No se conectó a CONTPAQi ni a Sierra Madre GMAO, no se usaron datos reales, no se publicaron puertos ni se hizo `git push`.

## 2. Respaldo y migración

| Concepto | Resultado |
|---|---|
| Respaldo previo | `var/backups/erp_minero_dev_20261119_124648.dump` |
| Tamaño / SHA-256 | 214141 bytes / `759532b6ffbe1cd53478a8cd491495f79cbdaeda53332fb11129813e4c5480ca` |
| Verificación | `pg_restore --list` correcto, 434 entradas |
| Revisión inicial | `a1b2c3d4e5f6` |
| Revisiones aplicadas | `b7c8d9e0f1a2`, `b7c8d9e0f1a3`, `c1d2e3f4a5b6`, `d2e3f4a5b6c7`, `e5f6a7b8c9d0` |
| Revisión final | `e5f6a7b8c9d0 (head)` |
| Integridad | 62 tablas, 144 índices, 231 llaves foráneas, `ck_location_map_no_exacto` presente |
| PostgreSQL | 17.12 en `127.0.0.1:5432` |

Lote 4 no agregó una migración de esquema: la cobertura RBAC se sincronizó con un comando administrativo aditivo sobre `erp_minero_dev`. No se eliminó ni sobrescribió ningún registro.

## 3. Servicios locales

| Servicio | URL | Observación |
|---|---|---|
| API FastAPI | <http://127.0.0.1:8000> | `GET /health` → `{"status":"ok","env":"local"}` |
| Documentación | <http://127.0.0.1:8000/docs> | Incluye `PATCH /api/v1/auth/username` |
| Frontend Vite | <http://localhost:5173> | Servidor de desarrollo |
| Proxy local | <http://127.0.0.1:8080> | Solo bucle local; sirve `frontend/dist` |

CORS queda limitado a `http://127.0.0.1:5173` y `http://localhost:5173`. No se usa `0.0.0.0`.

Para reiniciar API y proxy sin tocar Vite:

```powershell
cd E:\ERP_MINERO
python scripts/portal_ctl.py restart
```

## 4. Seguridad entregada

### Backend

- Rol `SUPERADMIN` con los 78 permisos del catálogo; `ADMIN_ROLE_CODES` incluye `SUPERADMIN` y `ADMIN`.
- Catálogo `PERMISSIONS_LOTE4`: `report.view`, `budget.view`, `budget.manage`, `system.settings.view`, `system.settings.manage`, `integration.manage`. Solo registra permisos; **no crea pantallas operativas falsas**.
- `PATCH /api/v1/auth/username`: exige contraseña actual, valida formato y duplicados, revoca otras sesiones y audita sin secretos.
- Protección del último superadministrador activo: no se puede desactivar, dar de baja ni quitarle el rol.
- Solo un `SUPERADMIN` puede asignar el rol `SUPERADMIN`.
- Comando `python -m app.modules.identity.bootstrap_admin`: usa `getpass` de forma interactiva o `--password-stdin`, solo opera sobre `erp_minero_dev`, es idempotente y nunca imprime ni persiste la contraseña.

### Cuenta maestra

- Usuario `admin`, estado `ACTIVE`, rol `SUPERADMIN`, 78 permisos.
- Hash Argon2id verificado en base; `must_change_password` quedó en `true` al crear la cuenta.
- Auditoría `SUPERADMIN_BOOTSTRAPPED` registrada por `system`.
- Durante la validación visual se cumplió el cambio obligatorio; la cuenta quedó con `must_change_password = false`, 0 intentos fallidos y sin bloqueo. La credencial vigente se conserva fuera del repositorio; la contraseña inicial temporal ya no es válida.
- No se encontraron secretos en `aud.audit_log` ni usuarios de prueba (`qa.*`) en `erp_minero_dev`.

### Frontend

- Menú **Administración → Seguridad** con Mi cuenta, Usuarios, Roles y Permisos.
- `Mi cuenta`: cambio de usuario con contraseña actual, cambio de contraseña con política robusta, sesiones activas y revocación.
- Roles y Permisos son catálogos de solo lectura; la asignación de roles sigue en Usuarios.
- Plegado del menú lateral y ajustes mínimos de estilo; se conservó el diseño previo.

## 5. Verificación automatizada

| Comando | Resultado |
|---|---|
| `python -m pytest -q` | 123 pruebas aprobadas |
| `ruff check app tests` | Sin errores |
| `mypy app --follow-imports=silent` | Sin errores en 80 archivos |
| `npm.cmd run test -- --run` | 32 pruebas aprobadas en 9 archivos |
| `npm.cmd run build` | Compilación correcta (57 módulos) |
| `python -m alembic current` | `e5f6a7b8c9d0 (head)` |

Pruebas nuevas: `tests/test_lote4_security.py` (9 pruebas: alta idempotente, escalamiento de roles, cambio de usuario con revocación, duplicados, bloqueo temporal, protección del último superadmin y acceso al mapa) y `src/features/security/MyAccount.test.tsx` (2 pruebas).

## 6. Validación visual

| # | Punto | Resultado |
|---|---|---|
| 1 | Acceso con cuenta maestra | Correcto; aviso de contraseña temporal mostrado |
| 2 | Cambio obligatorio de contraseña | Correcto; nueva sesión emitida y flag desactivado |
| 3 | Dashboard | Indicadores desde API local, sin valores inventados |
| 4 | Menú lateral | Incluye Seguridad; plegado operativo |
| 5 | Catálogo de materiales | 3 resultados con búsqueda; ficha disponible |
| 6 | Almacén | Disponibilidad, reservas, entregas y kardex; estados vacíos explícitos |
| 7 | Ubicaciones | 6 ubicaciones listadas y ficha lateral |
| 8 | Mapa 2D | Versión 1 cargada; aviso `Referencial · no es plano exacto` |
| 9 | QR | Token opaco `WMS:ALM_PRINCIPAL_DEMO:A-01-R1-1-01`; SVG resuelve |
| 10 | Requisiciones | Listado con documentos `REQ-LAG-2026-…` |
| 11 | Autorizaciones | Bandeja con partida pendiente |
| 12 | Compras | Generación de OC y recepción parcial disponibles |
| 13 | Usuarios / Roles / Permisos | `admin` con `SUPERADMIN`; 12 roles y 78 permisos |
| 14 | Mi cuenta | Identificación, contraseña y sesiones activas |
| 15 | Cerrar sesión | Redirección a `/login`; sesión invalidada |

Módulos sin implementar (reportes, presupuestos, configuración e integraciones) no aparecen en el menú: `/reportes` redirige al dashboard y no se simula información.

Evidencia: `var/evidencia_lote4/01_login.png`, `02_dashboard.png` y `03_almacen_virtual.png` (directorio ignorado por Git).

## 7. Limitaciones y siguiente paso

1. La restauración del respaldo se verificó con `pg_restore --list`; no se restauró sobre una base separada.
2. No se ejecutó literalmente `empty → head` por falta de permiso `CREATEDB`; se validó la cadena incremental y la revisión final en `erp_minero_dev`.
3. Reportes, presupuestos, configuración e integraciones existen solo como permisos de catálogo.
4. No hay cámara/escaneo QR, órdenes de movimiento ni plano exacto.
5. No se probó concurrencia transaccional con dos sesiones reales.
6. No se declaró producción, no se hizo `push` y no se modificaron CONTPAQi ni GMAO.

Siguiente paso: revisar la evidencia visual, decidir la política de rotación de la credencial maestra y, solo con autorización formal, preparar el perfil de piloto (`erp_minero_pilot`) en `127.0.0.1`.
