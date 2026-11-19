# Cierre Fase 4.5 — Base piloto aislada y preparación de intranet

**Fecha:** 2026-11-18  
**Ruta física:** `E:\ERP_MINERO`  
**Estado:** CIERRE LOCAL COMPLETADO. **Base piloto y LAN pendientes. NO APTO PARA PRODUCCIÓN.**  
**Commit de protección:** `28a8d8c Agrega portal web local, proxy inverso y autorizacion parcial de la Fase 4.5` (local, sin push).  
**Entregables de cierre:** se versionan localmente junto con la validación de `Host`/`Origin`; no se hizo push ni despliegue.

---

## 1. Resumen ejecutivo

- El portal local sigue funcionando en **`http://127.0.0.1:8080`**, con API detrás del proxy en `127.0.0.1:8000`. No se reconstruyó ni se movió.
- Se protegió el avance con un commit local de 26 archivos previamente revisados; no hay secretos reales versionados.
- **La base `erp_minero_pilot` NO existe.** Solo están `erp_minero_dev` y `erp_minero_test`. El rol `erp_minero_app` tiene `rolcreatedb=False` y `rolsuper=False`; no se cambiaron privilegios ni se ejecutó SQL administrativo.
- Se entregó al usuario el SQL exacto para una cuenta autorizada: `CREATE DATABASE erp_minero_pilot OWNER erp_minero_app;`.
- No se ejecutó la migración `empty -> head` sobre el piloto porque la base no existe. En desarrollo la revisión activa es `f4a7c1e2b3d6 (head)`.
- Se reejecutaron todas las verificaciones locales disponibles: **63 pruebas backend**, ruff y mypy limpios, **9 pruebas frontend**, build correcto y **18/18 verificaciones del portal**.
- Se agregó validación de `Host`/`Origin` en la API, con 3 pruebas nuevas, como control previo para una futura intranet. Sigue sin abrirse ningún puerto LAN.
- La preparación LAN es documentación y plantilla solamente. No hay TLS activo, DNS, firewall, certificados instalados ni escucha externa.

---

## 2. Protección del avance

| Acción | Resultado |
|---|---|
| Lectura de `AGENTS.md`, `docs/FASE4_RESULTADOS.md` y `docs/FASE45_INTRAnET.md` | Realizada antes de tocar código |
| `git status --short`, `git log`, `git diff`, `git diff --check` | Revisados; sin cambios ajenos sobrescritos ni errores de whitespace |
| Escaneo de secretos en 26 archivos pendientes | Sin secretos reales; dos coincidencias eran nombres de variables (`token = request_id_var.set`, `username, password = ...`) |
| `.env` y `.env.pilot` | Ignorados por Git (`git check-ignore` confirmado) |
| Commit local | `28a8d8c`, sin push |
| Commit de cierre | Incluye estos cuatro documentos, la validación `Host`/`Origin` y la actualización de evidencias; sin push |

No se hicieron `git push`, despliegues ni conexiones a CONTPAQi Comercial Premium 11.5.1 o Sierra Madre GMAO.

---

## 3. Estado de la base piloto

Verificación de solo lectura ejecutada desde la configuración local:

```text
BASES_ERP ['erp_minero_dev', 'erp_minero_test']
ROL_APP ('erp_minero_app', False, False)   # rolcreatedb, rolsuper
```

| Comprobación | Resultado |
|---|---|
| `erp_minero_pilot` existe | **No** |
| Uso de `erp_minero_dev` como sustituto | **No permitido, no realizado** |
| Cambio de privilegios a `erp_minero_app` | **No realizado** |
| `DROP`, `TRUNCATE`, `downgrade` o borrado de bases | **No realizado** |
| Comando SQL administrativo ejecutado por este proyecto | **Ninguno** |

Comando exacto pendiente para la cuenta administradora autorizada:

```sql
CREATE DATABASE erp_minero_pilot OWNER erp_minero_app;
```

Detalle completo en `docs/VALIDACION_BASE_PILOTO.md`.

---

## 4. Migración `empty -> head`

**Estado: NO EJECUTADA sobre el piloto**, por la ausencia de la base. No se puede afirmar que la migración desde vacío funcione en el piloto hasta que un administrador cree `erp_minero_pilot` y se ejecute `scripts\preparar_base_piloto.cmd`.

Referencia observable en desarrollo (`erp_minero_dev`), que **no sustituye** la prueba en el piloto:

```text
alembic current: f4a7c1e2b3d6 (head)
esquemas: aud, cost, doc, intg, inv, mdm, mnt, org, public, pur, req, seg, wfl
tablas base: 42 | índices: 86 | foreign keys: 144
restricciones no validadas: 0
```

La comprobación de esquema, índices, relaciones, integridad y aislamiento quedó documentada como checklist en `docs/VALIDACION_BASE_PILOTO.md`.

---

## 5. Verificaciones reejecutadas

Ejecutadas el 2026-11-18 después de agregar la validación de `Host`/`Origin` y reiniciar el portal local:

| Comando | Resultado |
|---|---|
| `python -m pytest -q` (`backend`) | **63 passed** (60 anteriores + 3 nuevas de `Host`/`Origin`) |
| `python -m ruff check .` (`backend`) | `All checks passed!` |
| `python -m mypy app` (`backend`) | `Success: no issues found in 62 source files` |
| `npm.cmd run test -- --run` (`frontend`) | **9 passed** |
| `npm.cmd run build` (`frontend`) | Correcto; `index-DrqUmDyg.js` 220.63 kB, `index-CV7EGAsi.css` 8.09 kB |
| `python scripts\portal_ctl.py restart` | Detención y arranque correctos |
| `python scripts\portal_ctl.py status` | `backend_health: true`, `portal_health: true`; listeners en 8000 y 8080 |
| `python scripts\verificar_portal.py` | **18/18 verificaciones correctas** |
| `python -m alembic current` (`backend`) | `f4a7c1e2b3d6 (head)` en desarrollo |
| `git diff --check` | Sin errores |

Advertencias observadas en pytest: avisos de deprecación de Starlette/httpx y de `HTTP_422_UNPROCESSABLE_ENTITY`. No afectan el resultado; quedan registradas como deuda técnica menor.

---

## 6. Matriz funcional solicitada

La columna **Local** significa `erp_minero_dev`/`erp_minero_test` con datos sintéticos y el portal en `127.0.0.1:8080`. La columna **Piloto** permanece sin verificar porque la base no existe.

| Requisito | Verificado localmente | Verificado contra `erp_minero_pilot` |
|---|---|---|
| Inicio y cierre de sesión | Sí: verificador 18/18 y prueba en navegador | No |
| Cookies `HttpOnly`, `SameSite`, CSRF | Sí: 18/18; sin `Secure` porque es HTTP local | No |
| `Host`/`Origin`/CSRF | Sí: 3 pruebas nuevas; `Host` ajeno → 400, `Origin` ajeno → 403 | No |
| RBAC | Sí: pruebas backend y menú por rol en navegador | No |
| Captura de requisiciones | Sí: suite Fase 4 y navegación en navegador | No |
| Autorización parcial | Sí: 2 pruebas frontend y cobertura backend | No |
| Reservas | Sí: suite backend de inventario/requisiciones | No |
| Surtidos parciales | Sí: suite backend de entregas | No |
| Seguimiento de compras | Sí: suite backend de compras | No |
| Bitácora de auditoría | Sí: suite backend y pantalla de auditoría | No |
| Persistencia tras reinicio | Sí: `portal_ctl.py restart` y `/auth/me` → 200 | No |

No se ejecutó ningún movimiento en CONTPAQi ni GMAO.

---

## 7. Preparación para LAN (no activada)

Ya preparado:

- `deploy/nginx/erp-minero.conf`: plantilla de proxy inverso con TLS, redirección HTTP→HTTPS, rutas relativas `/api/`, cabeceras de seguridad y logs. **No instalada**.
- `deploy/nginx/README.md`: pasos para sustituir nombre DNS, certificados y rutas por valores gestionados por infraestructura.
- `.env.pilot.example`: perfil aislado con `CORS_ALLOW_ORIGINS=`, `ALLOWED_HOSTS`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE` y `SECURITY_HSTS_ENABLED`.
- Backend: validación de `Host`/`Origin`, CSRF existente, CORS sin comodines y cabeceras de seguridad.
- Frontend: `VITE_API_URL` vacío para rutas relativas, mismo origen.
- Documentación de respaldo, recuperación, detención y reversión.

No realizado: apertura de puertos, cambio de firewall, instalación de certificados, configuración de DNS, inicio de nginx ni escucha en `0.0.0.0`.

Detalle en `docs/PLAN_PILOTO_LAN.md` y `docs/SEGURIDAD_DESPLIEGUE.md`.

---

## 8. Bloqueos y siguiente paso

1. Un administrador autorizado crea `erp_minero_pilot` con el SQL indicado.
2. Se copia `.env.pilot.example` a `.env.pilot` y se completan `DATABASE_URL`, `SECRET_KEY`, `DEMO_PASSWORD` y, cuando aplique, `ALLOWED_HOSTS`. El archivo no se versiona.
3. Se ejecuta `scripts\preparar_base_piloto.cmd` y se comprueban revisión, esquema, índices, FKs, integridad, semilla sintética y aislamiento.
4. Se inicia el portal con `python scripts\portal_ctl.py start --build --env-file .env.pilot` y se repite la matriz funcional de la sección 6 sobre el piloto.
5. Sólo después de autorización formal de infraestructura y seguridad se ejecuta el plan LAN.
6. El triple match OC–recepción–factura continúa pendiente desde la Fase 4.

**Conclusión:** queda documentado un cierre técnico local reproducible. No hay evidencia para declarar disponibilidad en intranet ni preparación para producción.
