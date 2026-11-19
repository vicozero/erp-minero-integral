# Validación de base piloto — `erp_minero_pilot`

**Fecha:** 2026-11-18  
**Estado:** BLOQUEADA. La base piloto no existe; no se ejecutaron migraciones, semilla ni pruebas sobre ella.  
**Principio:** `erp_minero_dev` y `erp_minero_test` **no** son sustitutos del piloto. No se eliminan, truncan ni sobrescriben bases.

---

## 1. Estado actual verificado

Consulta de solo lectura contra PostgreSQL local:

```text
BASES_ERP ['erp_minero_dev', 'erp_minero_test']
ROL_APP ('erp_minero_app', False, False)   # rolcreatedb=False, rolsuper=False
```

| Comprobación | Resultado |
|---|---|
| `erp_minero_pilot` existe | No |
| Rol de aplicación con `CREATEDB` | No |
| Privilegios globales modificados | No |
| Base creada/eliminada por este proyecto | No |
| SQL administrativo ejecutado | Ninguno |

---

## 2. Paso administrativo pendiente

Debe ejecutarlo una cuenta administradora autorizada, fuera del repositorio:

```sql
CREATE DATABASE erp_minero_pilot OWNER erp_minero_app;
```

No se solicita `CREATEDB` para `erp_minero_app`, no se reutiliza `erp_minero_dev` y no se conecta a CONTPAQi ni a GMAO.

---

## 3. Configuración aislada del entorno piloto

```powershell
cd E:\ERP_MINERO
copy .env.pilot.example .env.pilot
```

Editar **solo** `.env.pilot` (ignorado por Git):

```dotenv
DATABASE_URL=postgresql+psycopg://erp_minero_app:<password>@127.0.0.1:5432/erp_minero_pilot
SECRET_KEY=<secreto-local-generado>
DEMO_PASSWORD=<contraseña-ficticia>
CORS_ALLOW_ORIGINS=
ALLOWED_HOSTS=127.0.0.1,localhost,testserver
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax
SECURITY_HSTS_ENABLED=false
```

Reglas:

- Los marcadores `<password>`, `<secreto-local-generado>` y `<contraseña-ficticia>` deben sustituirse por valores propios; la plantilla no genera secretos.
- `DATABASE_URL` debe terminar exactamente en `/erp_minero_pilot`. El script lo valida y se detiene si apunta a otra base.
- Para HTTPS/LAN, `ALLOWED_HOSTS` se sustituye por el FQDN interno autorizado y se activan `SESSION_COOKIE_SECURE=true` y `SECURITY_HSTS_ENABLED=true`.
- Verificar que el archivo no se versiona: `git check-ignore -v .env.pilot`.

---

## 4. Ejecución pendiente de preparación

Una vez confirmada la creación de la base por el administrador:

```powershell
cd E:\ERP_MINERO
.\scripts\preparar_base_piloto.cmd
```

El script realiza, en este orden:

1. Verifica que `DATABASE_URL` apunte a `erp_minero_pilot` y que la base sea accesible.
2. Ejecuta `alembic upgrade head` con `ERP_ENV_FILE=.env.pilot`.
3. Ejecuta `alembic current`.
4. Siembra datos sintéticos mediante `app.db.seed.seed_demo_data`.

Si la base no existe, imprime el SQL anterior y termina con código 2. **No crea bases.**

Para aplicar sólo migraciones:

```powershell
python scripts\preparar_piloto.py --skip-seed
```

---

## 5. Checklist posterior a la migración (no ejecutado)

### 5.1 Conexión y revisión

```sql
SELECT current_database(), current_user;
SELECT version_num FROM alembic_version;
```

Resultado esperado: `erp_minero_pilot`, `erp_minero_app` y `f4a7c1e2b3d6`.

### 5.2 Esquemas, tablas, índices y relaciones

Referencia observada en `erp_minero_dev` con la misma revisión:

| Esquema | Tablas | Índices | FK |
|---|---:|---:|---:|
| `aud` | 1 | 2 | 1 |
| `cost` | 2 | 3 | 9 |
| `doc` | 5 | 10 | 11 |
| `intg` | 3 | 6 | 0 |
| `inv` | 3 | 7 | 16 |
| `mdm` | 3 | 6 | 10 |
| `mnt` | 1 | 2 | 5 |
| `org` | 5 | 10 | 19 |
| `public` | 1 | 1 | 0 |
| `pur` | 4 | 8 | 24 |
| `req` | 3 | 7 | 17 |
| `seg` | 8 | 18 | 21 |
| `wfl` | 3 | 6 | 11 |
| **Total** | **42** | **86** | **144** |

Consultas sugeridas en el piloto:

```sql
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  AND schema_name NOT LIKE 'pg_temp%'
ORDER BY 1;

SELECT table_schema, count(*)
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
GROUP BY table_schema
ORDER BY table_schema;

SELECT schemaname, count(*)
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
GROUP BY schemaname
ORDER BY schemaname;
```

La comparación debe hacerse contra la huella de `head`, no contra datos de producción.

### 5.3 Integridad de restricciones

```sql
SELECT n.nspname AS esquema, c.conname AS restriccion, c.contype AS tipo
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  AND NOT c.convalidated
ORDER BY 1, 2;
```

Resultado esperado: **0 filas**. En `erp_minero_dev` se verificó 0 filas con la misma revisión.

También deben ejecutarse las pruebas automatizadas que cubren las invariantes de cantidades, unicidad de `document_no`, idempotencia, bloqueos de stock y trazabilidad. Ya pasan en local (63 pruebas backend), pero **deben repetirse apuntando al piloto** antes de darlo por validado.

### 5.4 Semilla exclusivamente sintética

```sql
SELECT count(*) FROM seg.app_user WHERE username LIKE 'demo.%';
```

Resultado esperado: **9** cuentas ficticias (`demo.admin`, `demo.solicitante`, `demo.aprobador`, `demo.almacenista`, `demo.comprador`, `demo.jefe`, `demo.gerencia`, `demo.auditor`, `demo.temporal`). No se deben cargar exportaciones de CONTPAQi ni datos reales.

### 5.5 Aislamiento de entornos

```sql
SELECT datname
FROM pg_database
WHERE datname IN ('erp_minero_dev', 'erp_minero_test', 'erp_minero_pilot')
ORDER BY datname;
```

Criterios:

- Las tres bases deben aparecer como bases distintas.
- Cada proceso debe usar un perfil explícito: `.env` para desarrollo, `conftest.py` fuerza `erp_minero_test` en pruebas y `.env.pilot` para el piloto.
- Ninguna conexión debe cambiar de base en tiempo de ejecución.
- El portal contra el piloto se inicia con `python scripts\portal_ctl.py start --build --env-file .env.pilot`.

---

## 6. Registro de ejecución

| Ítem | Ejecutado | Motivo / evidencia |
|---|---|---|
| Creación de `erp_minero_pilot` | No | Requiere cuenta administradora autorizada |
| Configuración de `.env.pilot` | No | Base inexistente; plantilla lista |
| Migración `empty -> head` en piloto | No | Depende de la creación de la base |
| Verificación de esquema/índices/FKs en piloto | No | Depende de la migración |
| Consultas de integridad en piloto | No | Dependen de la migración |
| Siembra sintética en piloto | No | Dependen de la migración |
| Verificación de aislamiento dev/test/pilot | Parcial | Solo se confirmó que existen `dev` y `test`; falta `pilot` |
| Prueba funcional de requisición completa en piloto | No | Base inexistente |

---

## 7. Reversión

- No ejecutar `alembic downgrade`, `DROP DATABASE`, `TRUNCATE` ni borrado de filas sobre datos reales.
- Para detener el piloto, basta con detener los procesos del portal y dejar de pasar `--env-file .env.pilot`; `.env` de desarrollo no se modifica.
- Si se decide descartar la base piloto, debe hacerse mediante ticket y aprobación explícita del administrador de PostgreSQL.
- Los archivos generados (`.env.pilot`, `frontend/dist/`, `var/`) están fuera del control de versiones.
