# Plan de despliegue — Lote 8

**Estado:** propuesto, **no ejecutado**.  
**Fecha:** 20/11/2026  
**HEAD actual:** `8421472619a0c62f460b6d063e14a4f850186a72`  
**Cambios:** todos en el árbol de trabajo; sin commit ni push.  
**Principio:** ningún paso de este plan se ejecuta sin la autorización indicada en la Puerta 0.

Este documento es el plan que pediste que preparara. No modifica infraestructura, no expone servicios, no rota credenciales y no promueve nada a producción.

---

## 0. Puertas de autorización

| # | Requiere autorización para | Por qué es bloqueante |
|---|---|---|
| G1 | Hacer commit y push de los cambios | Sin artefacto versionado no hay despliegue reproducible; además estaba prohibido en la tarea original |
| G2 | Ventana de mantenimiento sobre `E:` | `Warning` / `Full Repair Needed` con `PGDATA` encima |
| G3 | Reparación/traslado de `PGDATA` | No se puede ejecutar `CHKDSK /F`, formatear ni mover datos sin ticket |
| G4 | Backfill de los 3 saldos heredados | No se aceptan ajustes automáticos de inventario sin decisión |
| G5 | Aplicar migraciones a `erp_minero_dev` | Base real; ahora está en `a2b3c4d5e6f7` |
| G6 | Rotar la credencial de desarrollo | No se imprimió ni rotó ninguna credencial |
| G7 | Exponer el portal fuera de `127.0.0.1` | Está prohibido publicar puertos o abrir firewall sin autorización |
| G8 | Declarar producción | No se hizo y sigue fuera del alcance aprobado |

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
5. Push sólo si la autorización **G1** lo incluye explícitamente.

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

Criterios de aceptación: 175 pruebas backend, 63 frontend, migración `empty -> head` en `e4f5a6b7c8d9`, 18/18 capturas con sesión 200, 0 secretos reales en el diff.

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

**Nota final:** este plan no se ejecutó. Está listo para ejecutarse por fases en cuanto se concedan las autorizaciones de la Puerta 0.
