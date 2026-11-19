# Plan de activación controlada del piloto en LAN

**Fecha:** 2026-11-18  
**Estado:** PREPARADO, NO ACTIVADO. No se abrió firewall, no se inició nginx, no se configuró DNS ni se instalaron certificados.  
**Alcance:** acceso posterior desde una segunda PC autorizada, sólo después de aprobación formal de infraestructura y seguridad.  
**No incluye:** producción, migración de CONTPAQi/GMAO, SSO ni exposición pública.

---

## 1. Topología objetivo

```text
PC autorizada (navegador)
   │  https://erp-minero.<dominio-interno>/
   ▼
nginx en el servidor del piloto   ← único socket expuesto a la LAN autorizada
   │  Termina TLS y aplica HSTS
   │  proxy_pass http://127.0.0.1:8000
   ▼
FastAPI en 127.0.0.1:8000         ← nunca expuesto a usuarios finales
   │  SQLAlchemy
   ▼
PostgreSQL en 127.0.0.1:5432 / erp_minero_pilot
```

El build de React se sirve desde el mismo origen que la API; `VITE_API_URL` queda vacío. No se usa CORS entre la UI y la API. `scripts\portal_proxy.py` sigue siendo el punto de entrada **solo local** (`127.0.0.1:8080`); en LAN lo sustituye nginx.

---

## 2. Requisitos previos (ninguno ejecutado)

| Requisito | Responsable | Estado |
|---|---|---|
| Creación de `erp_minero_pilot` | Administrador de PostgreSQL | Pendiente |
| Migración `empty -> head` y semilla sintética | Responsable del ERP | Pendiente, ver `docs/VALIDACION_BASE_PILOTO.md` |
| Nombre DNS interno o IP autorizada | Infraestructura/TI | Pendiente |
| Certificado TLS confiable para equipos autorizados | Infraestructura/TI | Pendiente |
| Regla de firewall restringida a la subred/autorizados | Infraestructura/TI | Pendiente; **no la aplica este proyecto** |
| Instalación y arranque de nginx desde la plantilla | Infraestructura/TI | Pendiente |
| Aprobación por escrito de prueba LAN | Seguridad/negocio | Pendiente |
| Respaldo y prueba de restauración | Infraestructura + ERP | Pendiente |
| Cuentas de prueba ficticias y RBAC revisado | Responsable del ERP | Parcial: local sí, piloto no |

---

## 3. Configuración ya preparada

| Archivo | Contenido útil | Estado |
|---|---|---|
| `deploy/nginx/erp-minero.conf` | Redirección 80→443, TLS 1.2/1.3, `server_name`, proxy a `127.0.0.1:8000`, cabeceras de seguridad, HSTS, logs, sin listados de directorio | Plantilla, no instalada |
| `deploy/nginx/README.md` | Instrucciones para reemplazar dominio, certificados y rutas | Listo |
| `.env.pilot.example` | Perfil aislado, CORS vacío, `ALLOWED_HOSTS`, cookies y HSTS | Plantilla, no copiada |
| `backend/app/main.py` | Validación de `Host` → 400, `Origin` → 403, CSRF existente, cabeceras de seguridad | Implementado y probado |
| `frontend/src/api/client.ts` | Rutas API relativas cuando `VITE_API_URL` está vacío | Implementado y verificado |

No se modifica `PORTAL_HOST` ni se activa `PORTAL_ALLOW_LAN`: en el modelo objetivo nginx es el único proceso con socket en la red.

---

## 4. Procedimiento de activación (sólo con autorización)

### Paso 1 — Base piloto

El administrador crea la base y el responsable del ERP ejecuta la validación:

```sql
CREATE DATABASE erp_minero_pilot OWNER erp_minero_app;
```

```powershell
cd E:\ERP_MINERO
copy .env.pilot.example .env.pilot
# Editar .env.pilot sin versionarlo
.\scripts\preparar_base_piloto.cmd
```

Verificar `f4a7c1e2b3d6`, esquema, índices, FKs, integridad, semilla sintética y aislamiento según `docs/VALIDACION_BASE_PILOTO.md`.

### Paso 2 — Perfil de aplicación para HTTPS

En `.env.pilot`, una vez conocido el FQDN autorizado:

```dotenv
DATABASE_URL=postgresql+psycopg://erp_minero_app:<password>@127.0.0.1:5432/erp_minero_pilot
SECRET_KEY=<secreto-local-generado>
DEMO_PASSWORD=<contraseña-ficticia>
CORS_ALLOW_ORIGINS=
ALLOWED_HOSTS=erp-minero.<dominio-interno>
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=strict
SESSION_COOKIE_DOMAIN=
SECURITY_HSTS_ENABLED=true
BACKEND_PORT=8000
PORTAL_HOST=127.0.0.1
PORTAL_PORT=8080
PORTAL_BACKEND_URL=http://127.0.0.1:8000
PORTAL_ALLOW_LAN=false
PORTAL_HTTPS=false
PORTAL_HSTS=false
VITE_API_URL=
```

`PORTAL_HTTPS=false` y `PORTAL_HSTS=false` son correctos porque ese proxy local no se usa en LAN; nginx termina TLS y añade HSTS.

### Paso 3 — Frontend y backend

```powershell
cd E:\ERP_MINERO\frontend
npm.cmd run build

cd E:\ERP_MINERO
python scripts\portal_ctl.py start --build --env-file .env.pilot
python scripts\verificar_portal.py
```

El backend debe seguir escuchando en `127.0.0.1:8000`. Verificar que no haya listeners en `0.0.0.0`.

### Paso 4 — nginx, DNS y firewall (ejecutado por infraestructura)

1. Copiar `deploy/nginx/erp-minero.conf` a la configuración gestionada de nginx.
2. Sustituir `erp-minero.intranet.example.invalid` por el FQDN autorizado.
3. Sustituir rutas de certificado, llave y logs por ubicaciones gestionadas. **Nunca versionar certificados ni llaves.**
4. Verificar sintaxis y recargar nginx.
5. Crear el registro DNS interno.
6. Abrir firewall únicamente al servidor del piloto y a las PCs autorizadas.
7. Confirmar que PostgreSQL y FastAPI no son alcanzables desde la red.

### Paso 5 — Prueba controlada desde la segunda PC

Con el certificado confiable ya instalado por infraestructura:

- `https://erp-minero.<dominio-interno>/` carga sin advertencia de certificado.
- Login y logout con cuentas ficticias.
- Cookie de sesión con `Secure`, `HttpOnly` y `SameSite=Strict`.
- Escritura sin `X-CSRF-Token` → 403.
- Cabecera `Host` ajena → 400; `Origin` ajeno → 403.
- RBAC: cuentas sin permiso no ven ni ejecutan acciones restringidas.
- Requisición completa: captura, autorización parcial, reserva, surtido parcial, seguimiento de compras y bitácora.
- Reinicio del portal y persistencia de la información.
- Sin errores 5xx; accesos y errores quedan en los logs acordados.

---

## 5. Validaciones de host, origen y CSRF

| Control | Implementación | Configuración requerida en LAN |
|---|---|---|
| Host | Middleware rechaza `Host` no incluido en `ALLOWED_HOSTS` con HTTP 400 | FQDN interno exacto |
| Origen | Si el navegador envía `Origin`, se valida su host contra la misma lista; si no coincide, HTTP 403 | El mismo FQDN |
| CSRF | Cookie legible + token en memoria; se exige `X-CSRF-Token` en escrituras | Sin cambios |
| CORS | Sin comodines; piloto con `CORS_ALLOW_ORIGINS=` vacío | Sin cambios, mismo origen |
| Cookies | `HttpOnly` y `SameSite` ya implementados | Añadir `Secure` |
| HSTS | Desactivado en local | Activar en HTTPS estable |

---

## 6. Respaldo y recuperación

### Respaldo lógico

Ejecutarlo en el servidor, sin guardar contraseñas en el comando ni en Git:

```powershell
$env:PGPASSWORD = '<password-local-autorizado>'
pg_dump -h 127.0.0.1 -p 5432 -U erp_minero_app -Fc `
  -f backups\erp_minero_pilot_YYYYMMDD.dump erp_minero_pilot
Remove-Item Env:\PGPASSWORD
```

Incluir además el directorio de adjuntos controlado `var\attachments`, que no vive en PostgreSQL. La política de retención la define infraestructura.

### Restauración segura

**Nunca restaurar sobre una base existente.** La recuperación se prueba en una base nueva creada por el administrador:

```powershell
$env:PGPASSWORD = '<password-local-autorizado>'
pg_restore -h 127.0.0.1 -p 5432 -U erp_minero_app `
  --dbname erp_minero_pilot_restore --no-owner --exit-on-error `
  backups\erp_minero_pilot_YYYYMMDD.dump
Remove-Item Env:\PGPASSWORD
```

Después de validar la restauración, se decide conservar o eliminar la base temporal mediante ticket aprobado. No se usa `DROP` sobre la base piloto original.

---

## 7. Detención y reversión

1. Infraestructura detiene el servicio nginx y retira la regla de firewall.
2. Si hay procesos locales del portal: `.\scripts\detener_portal.cmd`.
3. El portal local vuelve a usar `.env` si se inicia sin `--env-file .env.pilot`.
4. Se retira la configuración de nginx instalada por infraestructura; la plantilla del repositorio permanece intacta.
5. La base `erp_minero_pilot`, si existe, queda aislada. No se ejecuta `downgrade`, `DROP` ni `TRUNCATE` sin ticket y aprobación.
6. Se conservan logs y bitácora para el análisis posterior.

---

## 8. Criterios para no declarar producción

Aunque la prueba LAN sea exitosa, no se declara producción mientras falten:

- Decisión formal de migración del inventario oficial; CONTPAQi sigue siendo el sistema oficial.
- Política de respaldos probada y monitorización centralizada.
- Endurecimiento de login frente a fuerza bruta y decisión sobre SSO.
- Triple match OC–recepción–factura pendiente desde la Fase 4.
- Aprobación explícita de seguridad para usuarios reales y datos reales.
