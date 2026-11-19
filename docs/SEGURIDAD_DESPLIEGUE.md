# Seguridad de despliegue — Fase 4.5

**Fecha:** 2026-11-18  
**Estado:** CONTROLES LOCALES IMPLEMENTADOS; CONTROLES DE INTRANET PENDIENTES DE ACTIVACIÓN.  
**Regla permanente:** CONTPAQi Comercial Premium 11.5.1 sigue siendo el inventario y la contabilidad oficiales. El ERP es un espejo operativo.

---

## 1. Controles implementados y verificados

| Control | Evidencia |
|---|---|
| Sesión opaca de 256 bits, hash SHA-256 en PostgreSQL, cookie `HttpOnly` | Verificador del portal 18/18 |
| Token CSRF en memoria + cookie legible; exigido en escrituras | Sin token → 403; logout con token → 204 |
| Contraseñas hasheadas con Argon2id; contraseña demo desde variable no versionada | Código y configuración revisados |
| CORS sin comodines; piloto con `CORS_ALLOW_ORIGINS=` vacío | Configuración y middleware revisados |
| Validación de `Host` y `Origin` | 3 pruebas nuevas: 400, 403 y 200 |
| Cabeceras `nosniff`, `DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP y CSP | Verificador y `docs/PRUEBAS_PORTAL.md` |
| Proxy local restringido a loopback; `PORTAL_ALLOW_LAN=false` por defecto | `portal_proxy.py` y `status` |
| Límite de cuerpo, rechazo de `Transfer-Encoding`, rutas estáticas dentro de `dist` | `portal_proxy.py` |
| RBAC granular con alcance y bitácora inmutable | Suite backend y pantallas de auditoría |
| Autorización parcial por partida con decisión para todas las líneas | 2 pruebas frontend + cobertura backend |
| API y UI en el mismo origen; bundle sin URL hard-codeada | Verificador 18/18 |

No se registran contraseñas, tokens ni secretos en logs. El escaneo de archivos versionados no encontró credenciales reales.

---

## 2. Controles pendientes para intranet

| Control | Situación | Acción requerida |
|---|---|---|
| TLS confiable | No activo | Certificado gestionado por infraestructura e instalado en equipos autorizados |
| `Secure` en cookies | `false` en local | `SESSION_COOKIE_SECURE=true` sólo con HTTPS |
| HSTS | Desactivado | `SECURITY_HSTS_ENABLED=true` y HSTS en nginx después de verificar TLS |
| `ALLOWED_HOSTS` con FQDN | Valores locales | Sustituir por el nombre DNS interno autorizado |
| DNS y firewall | No configurados | Registro interno y regla restringida por infraestructura |
| Exposición | Solo `127.0.0.1` | nginx como único socket LAN; PostgreSQL y FastAPI en loopback |
| Fuerza bruta / SSO | Sin rate limiting ni SSO | Decisión de seguridad antes de usuarios reales |
| Respaldo y monitorización | Procedimiento documentado, no probado en piloto | Ejecutar respaldo y restauración de prueba |
| Datos reales | No utilizados | Prohibido sin autorización por escrito |

---

## 3. Perfil recomendado para HTTPS controlado

Sustituir marcadores por valores gestionados; **no versionar el archivo resultante**.

```dotenv
ENV=pilot
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

`PORTAL_HTTPS=false` y `PORTAL_HSTS=false` se mantienen porque en LAN no se usa el proxy Python local: nginx termina TLS y emite HSTS.

---

## 4. Registro, respaldo y recuperación

- Accesos HTTP: `var\log\portal_access.log` en local y los logs que defina infraestructura en nginx.
- Errores y operaciones: `var\log\backend.log`, `var\log\portal.log` y la bitácora `aud` de PostgreSQL.
- `X-Request-ID` se propaga y se refleja en la bitácora para correlacionar accesos y operaciones sensibles.
- La base piloto no debe restaurarse sobre sí misma. La recuperación se prueba en una base nueva, según `docs/PLAN_PILOTO_LAN.md` §6.
- Los adjuntos controlados están en `var\attachments` y deben incluirse en el respaldo.

---

## 5. Riesgos y bloqueos

1. **Bloqueo formal:** `erp_minero_pilot` no existe; no hay migración `empty -> head` ni validación funcional en piloto.
2. **Bloqueo de infraestructura:** sin DNS, certificado, firewall ni autorización de red no hay prueba LAN.
3. **Riesgo operativo:** no hay política probada de respaldo/restauración para el piloto.
4. **Riesgo de acceso:** sin endurecimiento de login ni SSO, no debe exponerse a usuarios reales.
5. **Riesgo funcional:** triple match OC–recepción–factura pendiente desde la Fase 4.
6. **Riesgo de datos:** está prohibido extraer información real de CONTPAQi o GMAO sin autorización por escrito.
7. **Riesgo de despliegue:** cualquier cambio de `PORTAL_HOST`, `PORTAL_ALLOW_LAN`, `0.0.0.0` o firewall requiere autorización explícita.

---

## 6. Checklist antes de cualquier acceso desde otra PC

- [ ] Base piloto creada por administrador y aislada.
- [ ] Migración `empty -> head`, esquema, índices, FKs, integridad y semilla sintética verificados.
- [ ] `.env.pilot` con `Secure`, HSTS, `ALLOWED_HOSTS` y CORS vacío.
- [ ] `npm.cmd run build` con `VITE_API_URL` vacío.
- [ ] nginx configurado desde la plantilla, con certificado confiable y logs.
- [ ] FastAPI y PostgreSQL escuchando sólo en loopback.
- [ ] Firewall restringido por infraestructura a equipos autorizados.
- [ ] Pruebas desde segunda PC: login, cookies, CSRF, host/origen, RBAC y requisición completa.
- [ ] Respaldo y restauración de prueba exitosos.
- [ ] Aprobación por escrito y decisión formal sobre inventario oficial.

**No declare el ERP listo para producción mientras falte alguno de estos puntos.**
