# Despliegue local en Windows — Portal ERP MINERO

**Audiencia:** responsable del despliegue del ERP en la PC local.
**Estado:** procedimiento para `127.0.0.1` únicamente. **No publicar en intranet ni modificar firewall, puertos ni sistemas externos.**
**Reversibilidad:** todos los pasos son aditivos. No se eliminan datos ni se sobrescribe `.env`.

---

## 1. Requisitos previos

| Requisito | Verificación |
|---|---|
| Python 3.12+ | `python --version` (se usó 3.13.14) |
| PostgreSQL 17 en `127.0.0.1:5432` | `Get-Service postgresql-x64-17` |
| Node 20+ y npm | `node --version`, `npm.cmd --version` (se usaron 24.15.0 / 11.12.1) |
| Dependencias backend e frontend | `pip install -e ".[dev]"` en `backend`; `npm.cmd ci` en `frontend` |
| Rol `erp_minero_app` con acceso a la base | sin `CREATEDB`; verificado `rolcreatedb=False` |

> El puerto 8000 (API) y 8080 (portal) deben estar libres. Comprobar con
> `Get-NetTCPConnection -State Listen -LocalPort 8000,8080`.

---

## 2. Configuración del entorno local

`backend/.env` (no versionado) ya existe para desarrollo. Para el piloto se usa un perfil aparte:

```powershell
cd E:\ERP_MINERO
copy .env.pilot.example .env.pilot
```

Editar **solo** `.env.pilot`:

- `DATABASE_URL`: debe terminar en `/erp_minero_pilot`.
- `SECRET_KEY`: valor propio generado localmente.
- `DEMO_PASSWORD`: contraseña ficticia para las cuentas demo.
- `CORS_ALLOW_ORIGINS=`: vacío; el portal usa mismo origen.
- `SESSION_COOKIE_SECURE=false`, `SECURITY_HSTS_ENABLED=false` mientras sea HTTP local.
- `VITE_API_URL=` vacío para que el bundle use rutas relativas.

El script `scripts\preparar_base_piloto.cmd` crea `.env.pilot` desde la plantilla si no existe, pero **no genera secretos**: hay que editarlos antes de continuar.

---

## 3. Creación de la base piloto (paso administrativo, pendiente)

El rol de aplicación **no tiene `CREATEDB`** y este proyecto no lo solicita. Un administrador de PostgreSQL debe ejecutar, fuera del repositorio:

```sql
CREATE DATABASE erp_minero_pilot OWNER erp_minero_app;
```

No reutilizar `erp_minero_dev` ni `erp_minero_test`. No conectar a CONTPAQi ni a ninguna base de producción.

Una vez creada:

```powershell
cd E:\ERP_MINERO
.\scripts\preparar_base_piloto.cmd
```

El script valida el nombre de la base, aplica `alembic upgrade head`, verifica la revisión y siembra datos **sintéticos**. Si la base no existe, se detiene con el procedimiento anterior y no intenta crearla.

---

## 4. Inicio y verificación

```powershell
cd E:\ERP_MINERO
.\scripts\iniciar_portal_local.cmd
```

Salida esperada:

```text
Compilando React (npm run build)…
Portal listo en http://127.0.0.1:8080
API detrás del proxy en http://127.0.0.1:8000
Logs en E:\ERP_MINERO\var\log
```

Abrir `http://127.0.0.1:8080` en el navegador de la PC. Verificar:

```powershell
.\scripts\verificar_portal.cmd
python scripts\portal_ctl.py status
```

El verificador comprueba 18 condiciones; todas deben mostrar `[OK]`.

Para usar el perfil piloto en el portal:

```powershell
python scripts\portal_ctl.py start --build --env-file .env.pilot
```

---

## 5. Operación habitual

| Acción | Comando |
|---|---|
| Ver estado | `python scripts\portal_ctl.py status` |
| Reiniciar | `python scripts\portal_ctl.py restart` |
| Detener | `.\scripts\detener_portal.cmd` |
| Verificar | `.\scripts\verificar_portal.cmd` |
| Logs | `var\log\backend.log`, `var\log\portal.log`, `var\log\portal_access.log` |
| PIDs | `var\run\backend.pid`, `var\run\portal.pid` |

Los PIDs y logs están dentro de `var/`, excluido de Git. El verificador no imprime contraseñas ni tokens.

---

## 6. Reversión

1. `.\scripts\detener_portal.cmd` — detiene ambos procesos; no toma posesión de puertos ajenos.
2. Si se usó el perfil piloto, basta con dejar de pasar `--env-file .env.pilot`. `.env` original no se modifica.
3. Los archivos generados son `frontend/dist/`, `var/` y `.env.pilot` (todos ignorados por Git). La base `erp_minero_pilot`, si se creó, queda aislada; **no ejecutar `downgrade`, `DROP` ni `TRUNCATE`** sin ticket y aprobación.
4. La plantilla `deploy/nginx/erp-minero.conf` no está instalada: no hay nada que desinstalar en nginx, firewall ni DNS.

---

## 7. Prohibiciones recordatorias

- No sustituir `127.0.0.1` por `0.0.0.0`.
- No publicar puertos con Docker ni abrir firewall.
- No ejecutar `git push`.
- No guardar `.env`, `.env.pilot`, certificados ni exportaciones de CONTPAQi en Git.
- No declarar el portal listo para producción mientras falte TLS, autorización de red y la migración `empty -> head`.
