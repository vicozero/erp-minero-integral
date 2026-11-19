# Evidencia de pruebas — Fase 4.5 (portal local)

**Fecha:** 2026-11-18
**Entorno:** Windows / PowerShell, Python 3.13.14, Node 24.15.0, npm 11.12.1, PostgreSQL 17.12 real, navegador Chromium integrado.
**Regla cumplida:** todo se ejecutó en `127.0.0.1`. No se hicieron pruebas LAN, despliegue ni `git push`.

---

## 1. Resumen de comandos

| Comando | Directorio | Resultado |
|---|---|---|
| `python -m pytest -q` | `backend` | **60 passed** |
| `python -m ruff check .` | `backend` | `All checks passed!` |
| `python -m mypy app` | `backend` | `Success: no issues found in 62 source files` |
| `npm.cmd run test -- --run` | `frontend` | **9 passed** (3 cliente API, 2 autorización parcial, 4 App) |
| `npm.cmd run build` | `frontend` | `✓ built`; `index-DrqUmDyg.js` 220.63 kB, `index-CV7EGAsi.css` 8.09 kB |
| `python scripts\portal_ctl.py start` | raíz | `Portal listo en http://127.0.0.1:8080` |
| `python scripts\verificar_portal.py` | raíz | **18/18 verificaciones correctas** |
| `python scripts\portal_ctl.py restart` | raíz | Detención y arranque correctos |
| `git diff --check` | raíz | Sin errores de whitespace (solo avisos LF→CRLF de Windows) |

---

## 2. Verificador del portal (18/18)

`scripts\verificar_portal.cmd` comprobó:

1. `GET /health` detrás del proxy → 200.
2. Cabeceras de seguridad presentes (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `CSP`).
3. `GET /health/db` → 200.
4. Rutas SPA `/`, `/login`, `/requisiciones` → 200 con `<div id="root">`.
5. Referencia al bundle React en `index.html`.
6. Recurso estático JS → 200 y `Content-Type` javascript.
7. Bundle sin `http://127.0.0.1:8000` hard-codeado (API relativa).
8. Login `demo.admin` a través del proxy → 200.
9. Cookie `erp_session` con atributo `HttpOnly`.
10. Cookie `erp_csrf` legible por JavaScript.
11. `SameSite` presente en `Set-Cookie`.
12. Sin atributo `Secure` en HTTP local.
13. Escritura sin `X-CSRF-Token` → 403.
14. Logout con CSRF válido → 204.
15. `GET /api/v1/auth/me` tras logout → 401.
16–18. Comprobaciones adicionales de estado y contenido del bundle.

No se imprimieron contraseñas ni tokens.

---

## 3. Prueba funcional en navegador

Realizada sobre `http://127.0.0.1:8080` con el navegador integrado, sin acceso a la API directa:

| Paso | Resultado |
|---|---|
| Carga de `/` sin sesión | Redirect a `/login`; formulario visible; única petición API `/api/v1/auth/me` → 401 (esperado). |
| Login `demo.admin` | 200; redirect a `/`; menú principal y rol «Administrador» visibles. |
| Menú «Requisiciones» | `/requisiciones`, heading correcto, sin fallos de red. |
| Menú «Autorizaciones» | `/autorizaciones`, heading correcto, sin fallos de red. |
| Menú «Almacén» | `/almacen`, heading correcto, sin fallos de red. |
| Menú «Compras» | `/compras`, heading correcto, sin fallos de red. |
| Menú «Historial» | `/historial`, heading «Historial y seguimiento». |
| Menú «Usuarios» | `/usuarios`, heading «Administración de usuarios». |
| Menú «Auditoría» | `/auditoria`, heading «Bitácora de auditoría». |
| «Cerrar sesión» | Redirect a `/login`; formulario disponible. |
| Reinicio del portal | Tras `portal_ctl.py restart` y recarga, dashboard sigue visible; `/api/v1/auth/me` → 200. |
| CSS responsive | El bundle cargado expone los breakpoints `max-width: 1100px`, `900px` y `640px` (verificado por CSSOM en la página). |

No se registraron errores 5xx ni fallos de transporte en ninguna ruta. El único mensaje de consola es el 401 inicial de `/auth/me` antes de iniciar sesión, que es el comportamiento esperado.

---

## 4. Autorización parcial por partida

Dos pruebas unitarias nuevas cubren el contrato de la UI:

- `envía la cantidad editada y deja en cero la partida no seleccionada`: verifica `approved_qty: '7.5'` para la línea 1 y `'0'` para la línea 2, con `decision: 'APPROVE'` en ambas.
- `al rechazar una partida conserva autorizadas las demás`: verifica `APPROVE` con la cantidad solicitada en la línea no rechazada y `REJECT` con motivo en la línea rechazada.

Motivación: el backend requiere una decisión por línea; omitir líneas no seleccionadas las dejaría sin autorizar por accidente. La UI envía siempre todas las partidas.

---

## 5. Lo que NO se verificó

| Pendiente | Motivo |
|---|---|
| Migración `empty -> head` | Requiere que un administrador cree `erp_minero_pilot`; `erp_minero_app` tiene `rolcreatedb=False`. No se creó la base ni se ejecutó el paso. |
| Pruebas desde otra PC / LAN | Fuera de alcance; no se abrió firewall ni se cambió `PORTAL_HOST`. |
| TLS real, HSTS y cookies `Secure` | Requieren certificados e infraestructura; plantilla `deploy/nginx/erp-minero.conf` no aplicada. |
| Triple match OC–recepción–factura | Pendiente desde Fase 4, no incluido en esta fase. |
| Datos reales de CONTPAQi o GMAO | Prohibido sin autorización por escrito. |

---

## 6. Hallazgos corregidos durante la fase

1. `portal_proxy.py` usaba `self._headers`, eliminado en Python 3.13. Se sustituyó por un registro propio de cabeceras enviadas; el error se detectó en la primera petición y se corrigió antes de declarar éxito.
2. `verificar_portal.py` consultaba `Cookie.httponly`, inexistente en `http.cookiejar`. Se cambió a `has_nonstandard_attr("HttpOnly")`.
3. `scripts\sembrar_datos_demo.cmd` fallaba de forma aislada con `NoReferencedTableError` porque no registraba todos los modelos. Se corrigió registrando `app.main` antes de sembrar y se volvió a ejecutar correctamente (`Datos demo sintéticos listos`).
4. `portal_ctl.py` podía dejar procesos huérfanos tras `restart`: el PID registrado moría pero el proceso que escuchaba seguía vivo, y el siguiente arranque reutilizaba ese servicio sin darse cuenta. Se corrigió terminando el árbol de procesos con `taskkill /T /F`, resolviendo el PID real del puerto con `Get-NetTCPConnection`, agregando una comprobación previa de puertos ocupados y reportando ambos PIDs en `status`. Verificado: tras `restart`, los PIDs de `status` coinciden con los propietarios de 8000 y 8080 y no quedan listeners duplicados.

---

## 7. Conclusión

El portal local quedó funcional y verificable de forma reproducible en la PC. **No hay evidencia que permita afirmar disponibilidad en intranet ni preparación para producción.** El bloqueo formal es la creación administrativa de la base piloto y, después, la decisión de infraestructura del Lote 10.
