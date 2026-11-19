# Fase 2 — Resultados de verificación

**Fecha:** 2026-11-18
**Ruta física de trabajo:** `E:\ERP_MINERO` (confirmada por el usuario; `C:\ERP_MINERO` no existe en este entorno)
**Estado:** COMPLETADA Y VERIFICADA en PostgreSQL 17.12 real. Sin datos reales ni credenciales versionadas.

---

## 1. Resumen ejecutivo

Se dejó operativa la Fase 2 completa:

- PostgreSQL 17.12 local, escuchando solo en `127.0.0.1:5432`.
- Rol exclusivo `erp_minero_app` (no superusuario) y base de desarrollo `erp_minero_dev`.
- Base aislada `erp_minero_test` para pruebas automatizadas.
- Autenticación `scram-sha-256` en `pg_hba.conf` (sin `trust`).
- Alembic con dos revisiones aditivas: esquemas y 37 tablas de dominio.
- FastAPI con `/health` y `/health/db`, configuración por entorno y sin secretos en logs.
- 26 pruebas automatizadas con PostgreSQL real (incluye concurrencia con `FOR UPDATE`).
- `ruff check .` y `mypy app` sin hallazgos.
- Scripts locales de arranque y verificación en `scripts/`.

No se modificaron CONTPAQi, Sierra Madre GMAO ni sistemas externos. No se usó SQLite como sustituto en la verificación de Fase 2.

## 2. Resolución del bloqueo previo

El bloqueo `0xC0000142` documentado anteriormente se resolvió **ejecutando OpenCode con privilegios de administrador** (`Admin=True`). Con esa elevación:

- el servicio `postgresql-x64-17` pudo iniciarse usando el cluster limpio `E:\erp_pgdata`;
- el cluster corrupto `C:\Program Files\PostgreSQL\17\data` **no se eliminó ni se modificó**;
- no fueron necesarios WSL ni Docker (no se instalaron distribuciones ni Docker).

Durante la ejecación de pruebas se observó un reinicio inesperado del servicio con excepción `0xc0000409` en `ucrtbase.dll`. Tras reiniciar el servicio, la suite completa pasó de forma estable. Se recomienda mantener monitorizado el evento; no se encontró correlación con los cambios de código ni con las migraciones.

## 3. Configuración de PostgreSQL

| Elemento | Valor |
|---|---|
| Versión | PostgreSQL 17.12 (x86_64-windows, MSVC 19.44.35229) |
| Servicio | `postgresql-x64-17`, `Running`, inicio `Automatic` |
| Cluster activo | `E:\erp_pgdata` (UTF-8, `America/Mexico_City`) |
| Escucha | `localhost`, puerto `5432` |
| Autenticación | `scram-sha-256` para `local` e IPv4/IPv6 loopback |
| Bases | `erp_minero_dev` (desarrollo), `erp_minero_test` (pruebas) |
| Rol de aplicación | `erp_minero_app`, `rolsuper = false` |
| Permisos | `CONNECT`, `USAGE`, `CREATE` únicamente en las bases propias |
| Superusuario | `postgres`, contraseña generada localmente y guardada fuera del repositorio |

Las contraseñas se generaron con `RNGCryptoServiceProvider` (32 bytes), se escribieron solo en `.env` (ignorado por Git) y en archivos temporales fuera del repositorio con ACL restringida. `.env.example` conserva únicamente el marcador `<password>`.

## 4. Cambios en el backend

| Archivo | Cambio |
|---|---|
| `backend/app/core/config.py` | Ruta absoluta a `.env`, validación de `postgresql+psycopg` y localhost, secretos con `repr=False` |
| `backend/app/db/session.py` | Motor exclusivamente PostgreSQL, `pool_pre_ping`, `check_database_connection()` |
| `backend/app/db/base.py` | `type_annotation_map` para `TIMESTAMPTZ` en todas las fechas |
| `backend/app/api/v1/routers/health.py` | `GET /health/db` sin filtrar URL, usuario ni errores |
| `backend/app/modules/organization/models.py` | CHECK booleano inválido eliminado; nombres UNIQUE únicos |
| `backend/app/modules/identity/models.py`, `master_data/models.py`, `documentation/models.py` | Nombres UNIQUE únicos |
| `backend/migrations/versions/0001_initial_schema.py` | Crea los 12 esquemas con `CreateSchema(if_not_exists=True)` |
| `backend/migrations/versions/d147e7ec92fb_tablas_iniciales_por_dominio.py` | DDL explícito de 37 tablas, FK, UNIQUE, CHECK e índices |
| `backend/migrations/script.py.mako` | Plantilla Alembic compatible con `ruff` |
| `backend/alembic.ini` | `path_separator = os` |
| `backend/tests/conftest.py` | Arnés PostgreSQL real, migraciones automáticas y aislamiento por transacción/savepoint |
| `backend/tests/test_postgres_phase2.py` | 8 verificaciones obligatorias de Fase 2 |
| `backend/tests/test_concurrency.py` | Concurrencia real habilitada con `FOR UPDATE` |

## 5. Esquema verificado en PostgreSQL

- Revisión Alembic: `d147e7ec92fb (head)`.
- Tablas de dominio: **37** en los esquemas `seg`, `org`, `mdm`, `doc`, `req`, `wfl`, `inv`, `pur`, `mnt`, `cost`, `intg`, `aud`.
- `public.alembic_version`: 1 tabla de control.
- `created_at`: `timestamp with time zone` en todas las tablas.
- Importes/cantidades: `numeric(18,4)` / `numeric(18,6)`; **0 columnas** `float`, `real` o `double precision` en esquemas de dominio.
- FK, UNIQUE y CHECK aplicados por la base de datos, verificados con pruebas.

## 6. Pruebas ejecutadas

```powershell
cd E:\ERP_MINERO\backend
pytest -q
ruff check .
mypy app
```

Resultado:

- `pytest -q`: **26 passed**.
- `ruff check .`: **All checks passed!**
- `mypy app`: **Success: no issues found in 59 source files**.

Cobertura adicional de Fase 2:

1. conexión PostgreSQL real con rol no superusuario;
2. migraciones aplicadas y tipos `TIMESTAMPTZ`/`NUMERIC` sin `FLOAT`;
3. CRUD de compañía sintética;
4. incumplimiento de FK rechazado;
5. `NOT NULL` y `UNIQUE` reforzados por PostgreSQL;
6. rollback explícito sin persistencia;
7. `/health`, `/health/db` y OpenAPI sin credenciales;
8. ausencia de credenciales en archivos versionados y `.env` ignorado;
9. numeración concurrente única con dos transacciones reales.

## 7. Scripts locales

- `scripts/iniciar_backend.cmd` — arranca Uvicorn en `127.0.0.1:8000`.
- `scripts/verificar_fase2.cmd` — servicio, revisión Alembic, pruebas, lint y type-check.
- `scripts/sembrar_datos_demo.cmd` — siembra datos **sintéticos** en `erp_minero_dev`.

## 8. Limitaciones y siguiente paso

- No se hizo commit ni push; todos los cambios siguen en el árbol de trabajo.
- No se integraron CONTPAQi ni Sierra Madre GMAO; siguen siendo sistemas externos.
- El inventario operativo del ERP **no es** el inventario oficial; CONTPAQi conserva esa autoridad.
- Se recomienda revisar el evento `0xc0000409` del servicio PostgreSQL si se repite, y ejecutar `scripts\verificar_fase2.cmd` antes de cada entrega.
