# Seguridad del portal — estado local y requisitos para intranet

**Fecha:** 2026-11-18
**Estado actual:** solo `127.0.0.1`. Sin exposición de red, sin TLS, sin firewall modificado.
**Principio:** el ERP es un espejo operativo. **CONTPAQi sigue siendo el inventario y la contabilidad oficiales.**

---

## 1. Controles ya implementados

### 1.1 Sesión y CSRF

- Token de sesión opaco de 256 bits entregado **solo** en cookie `HttpOnly`; en PostgreSQL se guarda `SHA-256`, nunca el token en claro.
- El navegador no guarda tokens en `localStorage`. El token CSRF se mantiene en memoria y se respalda en la cookie legible `erp_csrf`.
- El backend exige `X-CSRF-Token` coincidente en `POST/PUT/PATCH/DELETE` cuando autentica por cookie. Verificado: sin cabecera → **403**, con cabecera → **204** en logout.
- Contraseñas hasheadas con Argon2id. La contraseña demo se toma de `DEMO_PASSWORD` en un archivo no versionado; no hay credenciales en el repositorio.

### 1.2 Same-origin y CORS

- El bundle compilado usa rutas relativas (`VITE_API_URL` vacío). La API y la UI comparten origen en `127.0.0.1:8080`.
- `CORS_ALLOW_ORIGINS` por defecto solo permite los puertos de desarrollo de Vite en localhost; el perfil piloto lo deja vacío. No hay comodines ni `allow_origins=["*"]`.
- `ALLOWED_HOSTS` rechaza con HTTP 400 cualquier cabecera `Host` desconocida; si el navegador envía `Origin`, se valida su host y se rechaza con HTTP 403 cuando no coincide. El valor por defecto cubre solo loopback y `testserver`; en intranet debe sustituirse por el FQDN autorizado.
- `allow_credentials=True` pero con orígenes explícitos; `allow_methods` y `allow_headers` están acotados.

### 1.3 Cabeceras de respuesta

Tanto FastAPI como el proxy local envían:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Content-Security-Policy: default-src 'self'; base-uri 'self'; frame-ancestors 'none'; ...
```

`Strict-Transport-Security` solo se añade si `SECURITY_HSTS_ENABLED=true` / `PORTAL_HSTS=true`, y **debe activarse únicamente con HTTPS real**.

### 1.4 Proxy local

- `PORTAL_HOST` por defecto `127.0.0.1`. Si se cambia a una IP de red sin `PORTAL_ALLOW_LAN=true`, el proceso se detiene con error explícito.
- `PORTAL_BACKEND_URL` solo acepta HTTP en loopback.
- Límite de cuerpo de petición (`PORTAL_MAX_BODY_BYTES`, 20 MiB por defecto) y rechazo de `Transfer-Encoding` sin `Content-Length`.
- Las rutas estáticas se resuelven y se validan con `is_relative_to(dist)`; no se sirven archivos fuera del build.
- Se descartan cabeceras hop-by-hop y se reenvían `X-Forwarded-*` con información del cliente.

### 1.5 Autorización y trazabilidad

- RBAC con permisos granulares y alcance por empresa, unidad minera, departamento y almacén.
- La UI oculta enlaces sin permiso, pero la autoridad es el backend; rutas y operaciones separan ROLE_ACCESS.
- Bitácora inmutable con actor, acción, entidad, antes/después, `request_id` y correlación. Las decisiones de autorización y los movimientos de stock quedan registrados.
- Autorización parcial por partida envía decisión para **todas** las líneas; las no incluidas se dejan en cero con motivo, evitando autorizaciones implícitas.

---

## 2. Lo que NO está resuelto para intranet

| Riesgo | Situación actual | Acción requerida antes de intranet |
|---|---|---|
| HTTP sin cifrar | `http://127.0.0.1:8080` | TLS interno con certificado gestionado; `SESSION_COOKIE_SECURE=true`. |
| HSTS | Desactivado | Activar solo después de verificar HTTPS estable. |
| Exposición de red | Ninguna; solo loopback | Aprobación formal de infraestructura, firewall y nombre interno. La plantilla `deploy/nginx/erp-minero.conf` no está aplicada. |
| Fuerza bruta | No hay rate limiting ni backoff documentado en este alcance | Revisar endurecimiento de login antes de múltiples usuarios. |
| SSO | No implementado | Decidir si se integra con directorio institucional. |
| Base de datos | `erp_minero_dev` con datos sintéticos; piloto sin crear | Crear `erp_minero_pilot` por administrador, migrar `empty -> head` y sembrar solo datos sintéticos. |
| Integraciones | Sin conexión a CONTPAQi/GMAO | Mantener adapters, staging y outbox; nunca acceso directo a sus bases. |
| Respaldo / monitoreo | Fuera de alcance | Definir política con infraestructura. |

---

## 3. Checklist de intranet (no ejecutado)

1. Autorización por escrito de infraestructura y seguridad.
2. Certificado TLS y nombre interno definidos; nginx configurado desde `deploy/nginx/erp-minero.conf`.
3. Perfil de entorno con `SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_SAMESITE=strict` (o `lax`), `SECURITY_HSTS_ENABLED=true`, `CORS_ALLOW_ORIGINS=` vacío y `ALLOWED_HOSTS=<fqdn-interno-autorizado>`.
4. Frontend recompilado con `VITE_API_URL=` vacío.
5. Backend y PostgreSQL enlazados a `127.0.0.1`; nginx es el único socket expuesto.
6. Firewall configurado por el administrador de TI; **no** por este proyecto.
7. Repetir `scripts\verificar_portal.cmd` sobre `https://<host>/` y añadir pruebas desde otra PC autorizada.
8. Revisar bitácora, permisos por rol y política de contraseñas antes de dar acceso a usuarios reales.
9. Decisión formal sobre migración de inventario oficial: mientras tanto, CONTPAQi permanece como sistema oficial.

---

## 4. Reglas permanentes

- No guardar secretos, tokens, cadenas con contraseña, llaves ni certificados en Git.
- No usar `0.0.0.0`, no publicar puertos, no abrir firewall.
- No extraer datos reales de producción sin autorización por escrito.
- No eliminar ni reescribir movimientos contables o de inventario; las correcciones son contrapartidas o reversiones.
- No afirmar que el portal está listo para producción mientras falten TLS, autorización de red y la migración `empty -> head`.
