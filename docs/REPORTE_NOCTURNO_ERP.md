# Reporte nocturno del ERP · 18–19 noviembre 2026

## 1. Propósito y alcance

Misión nocturna con presupuesto máximo de seis horas para dejar un ERP **demostrable, visualmente profesional y verificable** en el entorno local. Prioridades aplicadas:

1. Integridad y seguridad.
2. Funcionalidad demostrable.
3. Calidad visual.
4. Funciones nuevas.

Se trabajó únicamente en `E:\ERP_MINERO`, sobre `127.0.0.1`, sin exposición de red, sin conexión a CONTPAQi ni GMAO, sin datos reales y sin `git push`.

## 2. Estado general

El portal queda operativo en `http://127.0.0.1:8080`, con API detrás del proxy en `http://127.0.0.1:8000`. **No se afirma que el sistema sea apto para producción**; es un entorno local de demostración con datos sintéticos.

| Verificación | Resultado real |
| --- | --- |
| `python scripts\verificar_portal.py` | **22/22** verificaciones correctas |
| Backend `pytest` | **68 passed**, 5 advertencias de deprecación no bloqueantes |
| Frontend `vitest` | **14/14** pruebas correctas en 5 archivos |
| `npm run build` | Correcto; bundle `index-QWrB8VnM.js`, CSS `index-BKVcMwy5.css` |
| `ruff check app tests` | `All checks passed!` |
| `mypy app` | `Success: no issues found in 65 source files` |
| Alembic | `f4a7c1e2b3d6 -> a1b2c3d4e5f6` aplicado |
| Semilla sintética | `Semilla demo aplicada correctamente.` |

## 3. Trabajo entregado

### 3.1 Modernización corporativa (commit previo `c80e14d`)

- Identidad visual unificada: tema claro/oscuro, cabeceras, paneles, tarjetas de métricas, tablas, badges y estados vacíos.
- Dashboard con métricas reales obtenidas de `api.requisitions()` y `api.purchases()`.
- Cinta explícita `DEMOSTRACIÓN · Datos sintéticos aislados`; el inventario se presenta como operativo, no oficial.

### 3.2 WMS Lote A (checkpoint de esta noche)

**Backend**

- Modelos nuevos en `mdm`: familias, referencias cruzadas, información de proveedor por artículo, fotos, restricciones de ubicación y series/lotes relacionados.
- Columnas aditivas `lot_ref_id` y `location_ref_id` en saldos de inventario; se conservan los campos centinela anteriores.
- Migración única `a1b2c3d4e5f6`, aditiva, con `downgrade()` protegido contra datos reales.
- `WmsCatalogService` con búsqueda combinable, ficha de material, ficha de ubicación, altas controladas y registro de fotos.
- Endpoint `/api/v1/wms/*` con permisos granulares y auditoría de las acciones sensibles.
- Fotos validadas por MIME, extensión, magic bytes y tamaño máximo de 2 MB; se almacenan bajo `var/item_photos/<item_id>/` con SHA-256.
- Semilla sintética de familias, artículos, lotes, series, proveedores, referencias y seis ubicaciones con existencias asignadas.

**Frontend**

- Nuevas rutas `/catalogo` y `/ubicaciones`, protegidas por permisos y visibles en el menú `WMS · Catálogo`.
- Pantalla de catálogo: búsqueda por texto/código/código de barras, filtros por familia, almacén, ubicación física, equipo y activo; ficha con dato técnico, saldos por ubicación, lotes, series, proveedores, referencias y movimientos.
- Pantalla de ubicaciones: filtros, tabla de ocupación derivada de saldos, altas controladas y ficha con restricciones, saldos y token legible de etiqueta.
- Pruebas nuevas: 2 de catálogo y 3 de ubicaciones, más la extensión del verificador de portal a 22 comprobaciones.

## 4. Evidencias

Archivos reales generados en `docs/evidencias_demo/`:

- `01_catalogo_ficha_material.txt`: texto renderizado por el navegador en `/catalogo`, sesión `demo.admin`, ficha de `DEMO-TORNILLO`.
- `02_ubicaciones_ficha.txt`: texto renderizado en `/ubicaciones`, ocupación de seis ubicaciones y ficha de `A-01-R1-1-01` con token `WMS:ALM_PRINCIPAL_DEMO:A-01-R1-1-01`.
- `03_verificacion_portal.txt`: salida de `python scripts\verificar_portal.py` → 22/22.
- `04_backend_pytest.txt`: salida de `pytest` → 68 passed.
- `05_frontend_vitest.txt`: salida de `vitest` → 14/14.

No se tomaron capturas de pantalla: la ventana del escritorio no estaba visible durante la ejecución nocturna. Se registró el texto real del DOM y el estado de red en su lugar; no se falsificaron imágenes.

## 5. Limitaciones y riesgos

- No existe la base de datos piloto `erp_minero_pilot`; no se ejecutó una migración `empty -> head` sobre un esquema limpio independiente.
- La normalización del CHECK con doble prefijo no se ejecutó: corregirlo exige recrear constraints sobre datos existentes y requiere aprobación explícita.
- El token WMS es legible e imprimible; **no** es un QR gráfico escaneable. Generación y lectura gráfica quedan para el Lote B.
- No se conectó ni modificó CONTPAQi Comercial Premium 11.5.1 ni Sierra Madre GMAO; no hay SDK o API verificada autorizada.
- Triple match OC–recepción–factura sigue pendiente.
- Decisiones de negocio pendientes: política de valuación, lotes/series obligatorios, jerarquía de ubicación, modelo de herramientas, esquema `wms` y aprobadores de diferencias/reversiones.
- LAN, TLS, DNS, firewall y certificados permanecen sin activar.
- No se emitió `git push`; el checkpoint es local.

## 6. Reproducción local

```powershell
cd E:\ERP_MINERO
python scripts\portal_ctl.py start --build
python scripts\verificar_portal.py
cd backend
python -m pytest --disable-warnings
python -m ruff check app tests
python -m mypy app
cd ..\frontend
npm.cmd run test -- --run
npm.cmd run build
```

## 7. Siguiente paso

Continuar con la Fase 3: pulir visualmente Requisiciones y Autorizaciones sin alterar las reglas transaccionales, y resolver primero las decisiones de negocio listadas en `docs/PLAN_SIGUIENTE_DESARROLLO.md`. El detalle visual del Lote A está en `docs/AVANCE_VISUAL_WMS.md`.

**Conclusión:** se entrega un avance estable y verificable en local, con evidencias reales y pendientes explícitos. No se declara apto para producción.
