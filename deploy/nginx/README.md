# Configuración de proxy inverso (plantilla, no aplicada)

`erp-minero.conf` es una referencia para el **Lote 10 (endurecimiento para intranet)** del plan. **No está instalada, no se ha iniciado nginx, no se abrió el firewall y no se expuso ningún puerto.**

Solo se usa después de una decisión formal de infraestructura y seguridad. Para ese momento:

1. Reemplazar `erp-minero.intranet.example.invalid` por el nombre interno autorizado.
2. Reemplazar las rutas de certificados y logs por ubicaciones gestionadas por infraestructura. Los certificados y llaves **nunca** se versionan.
3. Verificar que FastAPI siga enlazado a `127.0.0.1:8000`; nginx debe ser el único proceso con socket en la red interna.
4. Ajustar el perfil piloto/producción con `SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_SAMESITE=strict` (o `lax`) y `SECURITY_HSTS_ENABLED=true`, y recompilar el frontend con `VITE_API_URL` vacío para rutas relativas.
5. Repetir `scripts\verificar_portal.cmd` contra `https://<host>/` y ampliar las pruebas de red con autorización por escrito.

Mientras tanto, el portal local usa `scripts\portal_proxy.py` en `127.0.0.1:8080`, que cumple la misma función de servidor de estáticos + proxy inverso sin exponer red.
