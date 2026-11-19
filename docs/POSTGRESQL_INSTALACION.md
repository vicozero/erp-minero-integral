# PostgreSQL — instalación y configuración local (Fase 2)

**Fecha:** 2026-11-18
**Estado:** Instalación funcional y verificada. Base de desarrollo y base de pruebas operativas.

---

## 1. Instalación

El usuario autorizó instalar PostgreSQL 17 localmente porque no existía una instancia funcional:

- existía `C:\Program Files\PostgreSQL\17\data` con `PG_VERSION=17`, sin binarios ni servicio (cluster corrupto, **no eliminado**);
- se instaló `PostgreSQL.PostgreSQL.17` mediante `winget`;
- versión real: **PostgreSQL 17.12** (`PostgreSQL 17.12 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit`);
- también se instaló `7zip.7zip` 26.06 como herramienta de diagnóstico.

El fallo inicial `0xC0000142` se resolvió elevando OpenCode a administrador. No se usaron WSL ni Docker.

## 2. Configuración activa

| Elemento | Valor |
|---|---|
| Cluster activo | `E:\erp_pgdata` (creado con `initdb`, independiente del directorio corrupto) |
| Servicio | `postgresql-x64-17`, `Running`, `Automatic` |
| Binarios | `C:\Program Files\PostgreSQL\17\bin` |
| Escucha | `localhost` / `127.0.0.1`, puerto `5432` |
| Codificación | `UTF8` |
| Zona horaria | `America/Mexico_City` |
| Locale | `Spanish_Mexico.1252` |
| Autenticación | `scram-sha-256` en `local`, `127.0.0.1/32` y `::1/128` |
| Acceso remoto | Deshabilitado |
| Bases | `erp_minero_dev`, `erp_minero_test` |
| Rol de aplicación | `erp_minero_app` (`rolsuper = false`) |

La cadena de conexión real se guarda únicamente en `.env` (ignorado por Git). `.env.example` usa `<password>` como marcador.

## 3. Objetos creados

```sql
CREATE ROLE erp_minero_app LOGIN PASSWORD '<generado-localmente>';

CREATE DATABASE erp_minero_dev
    OWNER = erp_minero_app
    ENCODING = 'UTF8'
    TEMPLATE = template0;

CREATE DATABASE erp_minero_test
    OWNER = erp_minero_app
    ENCODING = 'UTF8'
    TEMPLATE = template0;
```

Permisos otorgados en cada base: `CONNECT` sobre la base y `USAGE`, `CREATE` sobre `public`.

`gen_random_uuid()` está disponible en PostgreSQL 17 sin `pgcrypto`. No se usa el superusuario `postgres` para la operación diaria del ERP.

## 4. Migraciones

```powershell
cd E:\ERP_MINERO\backend
alembic upgrade head
```

Revisiones:

1. `0001_initial_schema` — crea los esquemas `seg`, `org`, `mdm`, `doc`, `req`, `wfl`, `inv`, `pur`, `mnt`, `cost`, `intg`, `aud`.
2. `d147e7ec92fb_tablas_iniciales_por_dominio` — crea 37 tablas con DDL explícito, FK, UNIQUE, CHECK, índices, `TIMESTAMPTZ` y `NUMERIC`.

Ambas revisiones son aditivas. El downgrade está bloqueado salvo autorización explícita. La verificación de `empty → head` se realizó en `erp_minero_test`.

## 5. Verificación de conexión

```powershell
cd E:\ERP_MINERO\backend
python -c "from app.db.session import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT current_user, current_database(), current_setting(\'TimeZone\'), current_setting(\'server_encoding\')')).fetchone()); c.close()"
```

Resultado esperado:

```text
('erp_minero_app', 'erp_minero_dev', 'America/Mexico_City', 'UTF8')
```

También puede verificarse desde la API:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/health/db
```

## 6. Notas operativas

- No se exponen puertos ni se abre el firewall.
- No se conecta a CONTPAQi ni a Sierra Madre GMAO.
- No se ejecutaron `DROP`, `TRUNCATE`, borrados masivos ni `alembic downgrade` sobre datos reales.
- Si el servicio se detiene, reiniciarlo con `Start-Service postgresql-x64-17` desde PowerShell elevado.
- Para verificación completa: `scripts\verificar_fase2.cmd`.
