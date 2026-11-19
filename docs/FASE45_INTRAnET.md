# Fase 4.5 — Portal web centralizado, proxy inverso y base piloto

**Fecha:** 2026-11-18
**Ruta física:** `E:\ERP_MINERO`
**Estado:** IMPLEMENTADA Y VERIFICADA solo en `127.0.0.1`. **NO declarada apta para intranet ni producción.**
**Alcance:** servidor web, proxy inverso local, base piloto sintética, experiencia responsive, pruebas locales y documentación.
**Fuera de alcance:** firewall, puertos en red, SSO, TLS real, migración de CONTPAQi o Sierra Madre GMAO.

---

## 1. Objetivo

Dejar una PC Windows con un único punto de entrada web para el ERP, sin modificar sistemas externos ni exponer servicios. El usuario abre `http://127.0.0.1:8080`; un proxy inverso local sirve el React compilado y reenvía la API a FastAPI en `127.0.0.1:8000`.

```text
Navegador (solo esta PC)
   │  http://127.0.0.1:8080
   ▼
portal_proxy.py  ── estáticos: frontend/dist
   │             └─ /api, /health, /status, /docs → http://127.0.0.1:8000
   ▼
FastAPI (127.0.0.1:8000) ── SQLAlchemy ── PostgreSQL 127.0.0.1:5432
                                             ├─ erp_minero_dev  (desarrollo actual)
                                             └─ erp_minero_pilot (pendiente de creación por DBA)
```

Regla cumplida: **mismo origen**. El navegador no conoce el puerto 8000; no se usa CORS en el portal.

---

## 2. Cambios entregados

### 2.1 Backend

| Archivo | Cambio |
|---|---|
| `backend/app/core/config.py` | `ERP_ENV_FILE` para perfiles alternativos sin sobrescribir `.env`; `CORS_ALLOW_ORIGINS` configurable (por defecto solo Vite local); `SECURITY_HSTS_ENABLED` desactivado por defecto. |
| `backend/app/main.py` | CORS restringido a orígenes explícitos y middleware de cabeceras de seguridad (`nosniff`, `DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP, CSP). HSTS solo si se habilita con HTTPS. |

### 2.2 Frontend

| Archivo | Cambio |
|---|---|
| `frontend/src/api/client.ts` | `VITE_API_URL` opcional; si está vacío, todas las llamadas son relativas al mismo origen. Se mantiene cookie HttpOnly + token CSRF en memoria. |
| `frontend/vite.config.ts` | Proxy de desarrollo local hacia `127.0.0.1:8000`. **No es el servidor de intranet.** |
| `frontend/src/features/approvals/Approvals.tsx` | Autorización parcial por partida: cantidades editables, motivo general y por partida, y decisión enviada para **todas** las líneas (las no seleccionadas quedan en cero con motivo). |
| `frontend/src/styles.css` | Breakpoints para 1100 px, 900 px y 640 px: menú horizontal en tabletas, tablas con scroll, acciones flexibles en móvil. |

### 2.3 Servidor y scripts

| Archivo | Función |
|---|---|
| `scripts/portal_proxy.py` | Proxy inverso + servidor de estáticos. Falla si `PORTAL_HOST` no es loopback sin `PORTAL_ALLOW_LAN=true`. Bloquea `Content-Length` excesivo, rutas fuera de `dist`, y methods hop-by-hop. |
| `scripts/portal_ctl.py` | `start`/`stop`/`restart`/`status` con PID y logs en `var/run` y `var/log`. Espera activa de health checks antes de declarar éxito. |
| `scripts/verificar_portal.py` | 18 verificaciones de health, SPA, bundle, cookies, CSRF y cabeceras. |
| `scripts/iniciar_portal_local.cmd` | Compila React e inicia el portal. |
| `scripts/detener_portal.cmd` | Detiene portal y API. |
| `scripts/verificar_portal.cmd` | Ejecuta el verificador. |
| `scripts/preparar_piloto.py` / `scripts/preparar_base_piloto.cmd` | Validan la base `erp_minero_pilot`, aplican Alembic y siembran datos sintéticos. **No crean bases.** |
| `.env.pilot.example` | Perfil aislado para el piloto (gitignored salvo la plantilla). |
| `deploy/nginx/erp-minero.conf` | Plantilla futura de intranet con TLS. **No aplicada.** |

---

## 3. Arranque reproducible

```powershell
cd E:\ERP_MINERO
.\scripts\iniciar_portal_local.cmd
.\scripts\verificar_portal.cmd
```

Resultado esperado: `Portal listo en http://127.0.0.1:8080` y `18/18 verificaciones correctas`.

Detener:

```powershell
.\scripts\detener_portal.cmd
```

La base piloto requiere un paso administrativo previo. El rol `erp_minero_app` tiene `rolcreatedb=False`; ver `docs/DESPLIEGUE_WINDOWS.md` §3. **No se ejecutó ese paso y no se creó `erp_minero_pilot`.**

---

## 4. Resultados de verificación

| Verificación | Resultado |
|---|---|
| Backend `python -m pytest -q` | 60 passed |
| Backend `ruff check .` / `mypy app` | Sin errores / 62 archivos sin errores |
| Frontend `npm run test -- --run` | 9 passed (7 originales + 2 de autorización parcial) |
| Frontend `npm run build` | JS 220.63 kB, CSS 8.09 kB |
| `scripts\verificar_portal.cmd` | 18/18 correctas |
| Navegador en `127.0.0.1:8080` | Login, dashboard, 7 rutas del menú, logout correctos |
| Reinicio `portal_ctl.py restart` | Sesión y datos persistidos; `/api/v1/auth/me` → 200 |
| Migración `empty -> head` | **Pendiente**: requiere creación administrativa de `erp_minero_pilot` |
| Pruebas LAN | **No ejecutadas**, fuera de alcance |

Detalle completo en `docs/PRUEBAS_PORTAL.md`.

---

## 5. Limitaciones y siguiente paso

1. La base piloto aún no existe. Un administrador debe ejecutar `CREATE DATABASE erp_minero_pilot OWNER erp_minero_app;`; el rol de aplicación no puede hacerlo y este proyecto no solicita `CREATEDB`.
2. No se probó migración `empty -> head` porque depende del punto anterior. La migración actual de `erp_minero_dev` es `f4a7c1e2b3d6 (head)`.
3. No hay TLS, firewall, nombre interno ni SSO. La plantilla nginx es solo documentación.
4. El triple match OC–recepción–factura sigue pendiente desde la Fase 4.
5. No se hicieron `git commit`, `git push`, despliegue ni conexión a CONTPAQi/GMAO.

**Siguiente paso:** autorizar la creación de la base piloto, ejecutar `scripts\preparar_base_piloto.cmd`, repetir las migraciones y verificaciones, y sólo entonces evaluar el Lote 10 con infraestructura y seguridad.
