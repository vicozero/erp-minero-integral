# Plan de despliegue — Lote 8

**Estado:** propuesto; **sólo G1 ejecutado** (commit y push). Despliegue operativo no ejecutado.  
**Fecha:** 20/11/2026  
**HEAD auditado:** `8421472619a0c62f460b6d063e14a4f850186a72`  
**HEAD publicado:** `1ccedc7` en `vicozero/erp-minero-integral` (privado)  
**Cambios:** código fuente ya versionado y publicado; despliegue operativo aún no ejecutado.  
**Principio:** ningún paso de este plan se ejecuta sin la autorización indicada en la Puerta 0.

Este documento es el plan que pediste que preparara. No modifica infraestructura, no expone servicios, no rota credenciales y no promueve nada a producción.

---

## 0. Puertas de autorización

| # | Requiere autorización para | Por qué es bloqueante |
|---|---|---|
| G1 | Hacer commit y push de los cambios | **Ejecutado con autorización**: `7d7e267` y `1ccedc7` en repo privado |
| G2 | Ventana de mantenimiento sobre `E:` | `Warning` / `Full Repair Needed` con `PGDATA` encima |
| G3 | Reparación/traslado de `PGDATA` | No se puede ejecutar `CHKDSK /F`, formatear ni mover datos sin ticket |
| G4 | Backfill de los 3 saldos heredados | No se aceptan ajustes automáticos de inventario sin decisión |
| G5 | Aplicar migraciones a `erp_minero_dev` | Base real; ahora está en `a2b3c4d5e6f7` |
| G6 | Rotar la credencial de desarrollo | No se imprimió ni rotó ninguna credencial |
| G7 | Exponer el portal fuera de `127.0.0.1` | **Ejecutado con autorización sólo para la demo**: túnel HTTPS de ngrok al proxy en `127.0.0.1:8080`, sin exponer PostgreSQL ni el puerto 8000 |
| G8 | Declarar producción | No se hizo y sigue fuera del alcance aprobado |
| G9 | Hacer público el repo o publicar un sitio en GitHub Pages | **Ejecutado con autorización**: repo público y demo estática publicada en `vicozero.github.io/erp-minero-integral`; el backend NO se expuso |

---

## 1. Control de cambios

1. Verificar que no haya trabajo ajeno sin revisar:
   - `git status --short`
   - `git diff --check`
2. Revisar el diff completo, incluidos archivos nuevos:
   - migrations `c3d4e5f6a7b8` y `e4f5a6b7c8d9`
   - pruebas Lote 8 y evidencia visual
   - excluir PNG/PDF, `var/secrets/`, `.env` y plantillas referencia
3. Tras **G1**, hacer commit local en español, imperativo y específico, por ejemplo:
   - `Corrige reauditoría del Lote 8 y refuerza sesiones`
   - `Agrega versión de credencial a sesiones`
4. Crear tag local de entrega, por ejemplo `v0.1.0-lote8`.
5. Push ejecutado tras autorización **G1**: `origin/main` apunta a `https://github.com/vicozero/erp-minero-integral.git`.

---

## 2. Saneamiento de almacenamiento

Sólo tras **G2** y **G3**:

1. Respaldar `erp_minero_dev` y verificar el dump con restauración aislada.
2. Ejecutar análisis de disco en ventana autorizada. No ejecutar `CHKDSK /F` sin orden explícita.
3. Si el diagnóstico lo confirma, trasladar `PGDATA` a disco sano con procedimiento aprobado.
4. Reiniciar `postgresql-x64-17` y verificar:
   - servicio `Running`
   - conexión con el rol de aplicación
   - codificación UTF8
   - sin mensajes `PANIC` nuevos en el log

---

## 3. Base de datos

Estado actual de `erp_minero_dev`: revisión `a2b3c4d5e6f7`, 3 saldos agregados, 0 filas de detalle, 3 saldos sin conciliar.

Tras **G5**:

1. Aplicar en ventana controlada:
   - `c3d4e5f6a7b8` — corrige la CHECK de reservas (no es estrictamente aditiva; no modifica datos).
   - `e4f5a6b7c8d9` — añade `seg.user_session.credential_version` en `NULL` (fail closed).
2. No ejecutar `downgrade`, `DROP`, `TRUNCATE` ni `DELETE` masivo.
3. Tras **G4**, decidir por escrito si se aplica el backfill controlado de los 3 saldos heredados.
4. Verificar sólo lecturas:
   - revisión activa: `e4f5a6b7c8d9`
   - esquemas no `pg_*`: 15 (14 de negocio + `information_schema`)
   - tablas base: 59; vistas: 6
   - columna `credential_version` presente
   - estado de conciliación de los 3 saldos

---

## 4. Credenciales y configuración

Tras **G6**:

1. Rotar la credencial de desarrollo mediante el mecanismo aprobado. No guardarla en Git ni imprimirla.
2. Usar un perfil `ERP_ENV_FILE` separado, por ejemplo `.env.pilot`.
3. Configurar valores sin secretos en el repositorio:
   - `ALLOWED_HOSTS`: sustituir `testserver` y puertos locales por el FQDN autorizado.
   - `TRUSTED_PROXY_HOSTS`: Host real que el proxy envía al backend.
   - `CORS_ALLOW_ORIGINS`: vacío si el portal se sirve del mismo origen; si no, orígenes explícitos.
   - `PORTAL_HOST=127.0.0.1`, `PORTAL_ALLOW_LAN=false` hasta **G7**.
   - `SECURITY_HSTS_ENABLED=false` hasta que exista TLS.
4. Nunca sustituir `127.0.0.1` por `0.0.0.0` sin autorización.

---

## 5. Construcción y verificación previa

Ejecutar de nuevo, con el artefacto ya versionado:

```powershell
python -m ruff check app tests
python -m mypy app --follow-imports=silent
python C:\Users\Dell\AppData\Local\Temp\opencode\run_pytest_ephemeral.py
npx.cmd tsc --noEmit
npm.cmd run test -- --run
npm.cmd run build
python C:\Users\Dell\AppData\Local\Temp\opencode\verify_head_ephemeral.py
python C:\Users\Dell\AppData\Local\Temp\opencode\run_visual_ephemeral.py
```

Criterios de aceptación: 175 pruebas backend, 65 frontend (63 del Lote 8 + 2 nuevas de ruta base), migración `empty -> head` en `e4f5a6b7c8d9`, 18/18 capturas con sesión 200, 0 secretos reales en el diff.

El repositorio incluye `.github/workflows/ci.yml`, que repite en GitHub Actions el bloqueo de backend (Ruff, Mypy y Pytest sobre PostgreSQL 17 efímero) y de frontend (TypeScript, Vitest y build). Las versiones de dependencias usadas por CI se fijan en `.github/ci-constraints.txt`. El workflow no publica la aplicación ni expone servicios: usa sólo datos sintéticos y `127.0.0.1` dentro del runner.

---

## 6. Despliegue local temporal

Sin **G7**, el único despliegue permitido es en loopback:

1. `uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. `python scripts/portal_proxy.py` con `PORTAL_HOST=127.0.0.1`, `PORTAL_PORT=8080`
3. Pruebas de humo:
   - `GET /health` → 200
   - `POST /api/v1/auth/login` → 200
   - `GET /api/v1/auth/me` con cookie → 200
   - `GET /` en el portal → contenido real
4. Al terminar la verificación, detener ambos procesos. No dejar escuchas permanentes sin autorización.

---

## 7. Promoción a intranet

Sólo tras **G7** y **G8**:

1. Definir FQDN autorizado y alcance de red.
2. Configurar TLS y cabeceras de seguridad antes de habilitar HSTS.
3. Ajustar `ALLOWED_HOSTS`, `TRUSTED_PROXY_HOSTS` y `CORS_ALLOW_ORIGINS` al FQDN real.
4. Abrir firewall únicamente para la subred autorizada.
5. Publicar el artefacto versionado; no reconstruir desde el árbol de trabajo.
6. Mantener vigilancia de logs de auditoría, sesiones y errores HTTP ≥400.
7. Registrar quién aprobó cada puerta y la ventana de cambio.

---

## 8. Verificación final y cierre

- [ ] Commit/tag creados y push autorizado o diferido.
- [ ] `E:` reparada o traslado de `PGDATA` aprobado.
- [ ] Revisiones `c3d4e5f6a7b8` y `e4f5a6b7c8d9` aplicadas a la base correcta.
- [ ] Decisión de backfill registrada.
- [ ] Credencial rotada con autorización.
- [ ] Configuración de Host/Origen/proxy ajustada al FQDN.
- [ ] Suite backend, frontend, build, migración y visual en verde.
- [ ] Sin secretos ni datos reales en el diff.
- [ ] Sin conexión a CONTPAQi ni GMAO.
- [ ] `docs/RESULTADOS_LOTE8_ESTABILIZACION.md` actualizado con la fecha y revisión de despliegue.

---

## 9. Reversión

No existe `downgrade` automático permitido. La reversión segura es:

1. Detener la aplicación.
2. Restaurar el dump verificado en un clúster aislado.
3. Validar que la restauración es correcta antes de redirigir tráfico.
4. No borrar, truncar ni sobrescribir datos reales.

---

## 10. GitHub Pages — demo estática publicada

Decisión del usuario: **publicar la demo**. La cuenta es plan **Free** y el repositorio se hizo **público** con autorización explícita (Puerta G9).

| Elemento | Estado real |
|---|---|
| Repositorio | `vicozero/erp-minero-integral`, **público**. No hay secretos ni datos reales en el árbol versionado. |
| Sitio | `https://vicozero.github.io/erp-minero-integral/` — HTML y asset JS verificados con HTTP 200. |
| Settings → Pages | Activado con `build_type: workflow` (source *GitHub Actions*), HTTPS forzado. |
| `.github/workflows/pages.yml` | Disparo **manual** (`workflow_dispatch`). Ejecutado una vez: `44839529279`, **success**. |
| `frontend/vite.config.ts` | `VITE_PUBLIC_BASE` por defecto `/`; el build de Pages usa `/erp-minero-integral/`. |
| `frontend/src/api/client.ts` | Sin cambios: usa `/api/v1` relativo cuando `VITE_API_URL` está vacío. En Pages apuntaría a `vicozero.github.io/api/v1` y fallaría. |

Se agregaron 2 pruebas de la ruta base (`frontend/src/test/viteConfig.test.ts`). Verificación local: `tsc` limpio, **65/65 pruebas frontend** en 17 archivos y build correcto tanto con base `/` como con `/erp-minero-integral/`.

**Limitación funcional:** GitHub Pages sirve archivos estáticos; no ejecuta FastAPI, PostgreSQL ni el proxy inverso. No existen `/api/v1`, `/health`, `/docs` ni autenticación. El sitio publicado es una **demo estática sin datos**: el formulario de acceso no funciona. Para un despliegue real hace falta un backend accesible por HTTPS con CORS y cookies `SameSite=None; Secure`, además de la base de datos; eso sigue supeditado a G7/G8.

**Siguiente paso:** configurar `VITE_API_URL` con el backend autorizado y volver a ejecutar el workflow manual. No se declaró producción. Para acceso con login se habilitó además una demo por túnel HTTPS, documentada en `docs/ACCESO_INTERNET_DEMO.md`.

---

## 11. Demo con acceso por Internet

Con autorización del usuario (Puerta G7) se levantó una demo temporal:

- URL pública: `https://unasked-edwardo-unclerkly.ngrok-free.dev` (túnel ngrok HTTPS al proxy del portal en `127.0.0.1:8080`).
- API FastAPI en `127.0.0.1:8000`, base PostgreSQL efímera `erp_internet_demo` con datos sintéticos, migrada a `head` y sembrada.
- Verificado: portal 200, `/health` ok, login de `demo.admin` 200 y `/api/v1/auth/me` con cookie de sesión.
- No se expuso PostgreSQL ni el puerto 8000; no se tocó `erp_minero_dev`.

Detalles, credenciales y limitaciones en `docs/ACCESO_INTERNET_DEMO.md`.

---

**Nota final:** el código fuente está publicado en un repositorio público, la demo estática está en GitHub Pages y hay una demo con login accesible por túnel HTTPS. El despliegue operativo del plan **no** se ejecutó: siguen pendientes las puertas G2–G6 y G8 (disco `E:`, backfill y migraciones, credencial y decisión de producción).
