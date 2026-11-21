# Acceso de demostración por Internet

**Fecha:** 20/11/2026  
**Estado:** demo temporal con datos sintéticos. **No es producción.**

## URL pública

`https://unasked-edwardo-unclerkly.ngrok-free.dev`

Es un túnel HTTPS de ngrok hacia el proxy del portal en este PC. La primera visita muestra la pantalla de advertencia de ngrok; pulse **Visit Site** para continuar.

## Cómo entrar

1. Abra la URL pública y acepte la advertencia de ngrok.
2. En el portal, use una de las cuentas ficticias documentadas en `docs/MANUAL_LOGIN_ADMINISTRACION.md` (por ejemplo `demo.admin`).
3. La contraseña es la generada para esta demo, **no está versionada**; se entregó fuera del repositorio y quedó sólo en el estado local del túnel.
4. El sistema pedirá cambiarla. La política permite una contraseña de **mínimo 6 caracteres**, con mayúscula, minúscula, número y carácter especial.

## Arquitectura de esta demo

| Capa | Ubicación | Observación |
|---|---|---|
| Navegador | Internet | Mismo origen para frontend y API: el dominio de ngrok. |
| Portal | `127.0.0.1:8080` | `scripts/portal_proxy.py` sirve `frontend/dist` y proxya `/api`, `/health` y `/docs`. |
| API | `127.0.0.1:8000` | FastAPI con `SESSION_COOKIE_SECURE=true` y `SameSite=lax`. |
| Base de datos | Clúster PostgreSQL efímero en `127.0.0.1` | `erp_internet_demo`, datos sintéticos, migrado a `head` y sembrado. **No es `erp_minero_dev`.** |

El proxy envía `X-Forwarded-Host` y `X-Forwarded-Proto=https`; el backend acepta el host público del túnel en `ALLOWED_HOSTS`. No se expuso PostgreSQL ni el puerto 8000 directamente.

## Verificación realizada

- `GET /` → 200, título `ERP MINERO INTEGRAL`, asset JS → 200.
- `GET /health` → `ok`.
- `POST /api/v1/auth/login` con `demo.admin` → 200 y token CSRF.
- `GET /api/v1/auth/me` con la cookie de sesión → `demo.admin`, rol `ADMIN`.

## Limitaciones y siguientes pasos

- El túnel depende de que este PC siga encendido y con los tres procesos activos. Si se reinicia, la URL pública cambia y hay que actualizar `ALLOWED_HOSTS` y la documentación.
- Los datos son sintéticos. CONTPAQi sigue siendo el inventario oficial; no se conectó a CONTPAQi ni a Sierra Madre GMAO.
- No se declaró producción. Siguen pendientes las puertas G2–G6 y G8 del plan de despliegue.
- Para un acceso permanente hace falta un proveedor de hosting con HTTPS, base de datos administrada y secretos gestionados; el repositorio tiene `Render CLI` instalado pero sin sesión, y `DATABASE_URL` hoy valida sólo `127.0.0.1`, por lo que ese paso requiere cambios de código y autorización adicional.
